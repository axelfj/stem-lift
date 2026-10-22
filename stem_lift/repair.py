"""
Repair Ready: basic restoration without AI, like the classic repair modules.

- declick:  clicks and pops are found where the second difference of the signal leaves its local
            robust range (median absolute deviation) and are rebuilt by cubic interpolation from the
            clean samples on both sides.
- declip:   runs of samples stuck at the clipping level are rebuilt with the cosine arc (or a cubic
            Hermite curve) that matches the value and slope of the waveform on both sides, then the
            whole file is scaled down so the rebuilt peaks fit; the applied gain is reported.
- dehum:    50 / 60 Hz (or auto) and its harmonics are measured block by block (amplitude and phase)
            and subtracted, after refining the exact mains frequency from the file itself.

Order inside repair(): clipping is located first so that its hard edges are not mistaken for
clicks, then clicks are rebuilt, then clipped runs, then the hum is removed.

Samples are float arrays shaped (frames, channels), as in audio.py. Everything is offline (whole
file), so the filters can be zero-phase and the detectors can look ahead.
"""
import numpy as np
from scipy import signal  # noqa: F401  (kept for the optional filters below)


# --------------------------------------------------------------------------- de-click

def find_clicks(x, sensitivity=1.0, max_width=24, protect=None):
    """
    Boolean mask of click samples for a mono signal.
    sensitivity 0.5 .. 2: higher finds more (the threshold is 14 / sensitivity robust sigmas).
    `protect` (optional boolean mask) marks samples that are not clicks even if they look like it,
    e.g. the hard edges of clipped runs; they are never flagged or rebuilt here.
    """
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[0]
    if n < 8:
        return np.zeros(n, dtype=bool)
    # Second difference: smooth signals stay tiny, impulses jump.
    e = np.zeros(n)
    e[2:] = x[2:] - 2.0 * x[1:-1] + x[:-2]
    # Local robust scale (median absolute deviation over ~50 ms blocks).
    block = 2048
    scale = np.empty(n)
    for start in range(0, n, block):
        seg = np.abs(e[start:start + block])
        # Flat (digital-silent or clipped) samples have a second difference of exactly zero; leave
        # them out, or a heavily clipped block would get a zero scale and flag everything.
        moving = seg[seg > 0.0]
        mad = np.median(moving) * 1.4826 if moving.size >= 16 else 0.0
        floor = 1e-4 * float(np.max(np.abs(x[start:start + block]), initial=0.0))
        scale[start:start + block] = max(mad, floor, 1e-7)
    # Soften block edges so the threshold does not step.
    scale = signal.medfilt(scale, kernel_size=1) if n < 4 else scale
    threshold = (14.0 / max(sensitivity, 0.1)) * scale
    mask = np.abs(e) > threshold
    if protect is not None:
        mask &= ~protect
    if not mask.any():
        return mask
    # Grow each detection by two samples on each side and drop runs wider than max_width (not clicks).
    grown = mask.copy()
    for k in (1, 2):
        grown[k:] |= mask[:-k]
        grown[:-k] |= mask[k:]
    out = np.zeros(n, dtype=bool)
    for start, stop in _runs(grown):
        if stop - start <= max_width:
            out[start:stop] = True
    if protect is not None:
        out &= ~protect
    return out


def _runs(mask):
    """[(start, stop), ...] of the True runs in a boolean array."""
    if not mask.any():
        return []
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    starts = np.flatnonzero(d == 1)
    stops = np.flatnonzero(d == -1)
    return list(zip(starts.tolist(), stops.tolist()))


def interpolate_gaps(x, mask, context=8):
    """Rebuilds the masked samples of a mono signal with a cubic spline through the clean neighbours."""
    y = np.array(x, dtype=np.float64, copy=True)
    n = y.shape[0]
    for start, stop in _runs(mask):
        lo = max(0, start - context)
        hi = min(n, stop + context)
        idx = np.concatenate((np.arange(lo, start), np.arange(stop, hi)))
        idx = idx[~mask[idx]] if idx.size else idx
        if idx.size < 4:
            # Nothing clean around: fall back to a straight line between the edges (or zero).
            a = y[start - 1] if start > 0 else 0.0
            b = y[stop] if stop < n else 0.0
            y[start:stop] = np.linspace(a, b, stop - start + 2)[1:-1]
            continue
        k = 3 if idx.size >= 4 else 1
        from scipy.interpolate import make_interp_spline
        spline = make_interp_spline(idx, y[idx], k=k)
        y[start:stop] = spline(np.arange(start, stop))
    return y


def declick(samples, sensitivity=1.0, protect=None):
    """Returns (repaired, number_of_clicks). Works per channel. `protect` as in find_clicks."""
    x = np.asarray(samples, dtype=np.float32)
    mono = x.ndim == 1
    x2 = x[:, None] if mono else x
    p2 = None if protect is None else (protect[:, None] if protect.ndim == 1 else protect)
    out = np.empty_like(x2)
    count = 0
    for c in range(x2.shape[1]):
        mask = find_clicks(x2[:, c], sensitivity, protect=None if p2 is None else p2[:, c])
        count += len(_runs(mask))
        out[:, c] = interpolate_gaps(x2[:, c], mask) if mask.any() else x2[:, c]
    return (out[:, 0] if mono else out), count


# --------------------------------------------------------------------------- de-clip

def find_clipped(x, threshold=None, min_run=4):
    """
    Mask of clipped samples. Auto mode (threshold None): runs of at least `min_run` samples sitting
    at the clipping level, identical to within 0.004 % of the peak. The level is the highest flat
    run found (so a stray click above the clipping level does not hide it); a natural peak is curved
    (even a 40 Hz sine moves more than that over four samples), so it is left alone. With an
    explicit `threshold`, every run of two or more samples at or above it counts.
    """
    x = np.asarray(x, dtype=np.float64)
    peak = float(np.max(np.abs(x), initial=0.0))
    if peak <= 0.0:
        return np.zeros(x.shape[0], dtype=bool)
    if threshold is None:
        level, shortest = _flat_level(x, peak, min_run) * (1.0 - 4e-5), min_run
    else:
        level, shortest = float(threshold), 2
    mask = np.abs(x) >= level
    out = np.zeros_like(mask)
    for start, stop in _runs(mask):
        if stop - start >= shortest:
            out[start:stop] = True
    return out


def _flat_level(x, peak, min_run):
    """
    Highest level (as |x|) at which the signal sits flat for at least `min_run` samples, looking only
    at the loud part of the file (above a quarter of the peak). Returns the peak when nothing is flat.
    """
    a = np.abs(x)
    flat = np.abs(np.diff(a)) <= 4e-5 * peak
    flat &= a[1:] >= 0.25 * peak
    best = 0.0
    for start, stop in _runs(flat):
        if stop - start >= min_run - 1:
            best = max(best, float(np.mean(a[start:stop + 1])))
    return best if best > 0.0 else peak


def _edge_slope(y, idx, direction, context=6):
    """
    Slope of y at sample idx, from a quadratic fitted to the `context` clean samples on the
    `direction` side (+1 forward / -1 backward), evaluated at idx itself.
    """
    n = y.shape[0]
    if direction < 0:
        lo, hi = max(0, idx - context + 1), idx + 1
    else:
        lo, hi = idx, min(n, idx + context)
    if hi - lo < 3:
        if hi - lo < 2:
            return 0.0
        return float(y[hi - 1] - y[lo])
    t = np.arange(lo, hi, dtype=np.float64) - idx
    coeffs = np.polyfit(t, y[lo:hi], 2)
    return float(coeffs[1])   # derivative of a t^2 + b t + c at t = 0


def _cosine_peak(level, slope, length):
    """
    Half-angle theta of a cosine arc A cos(w t) that passes `level` at both ends of a run of
    `length` samples with edge slope `slope` (magnitude): theta tan(theta) = slope * length / (2 level).
    Returns (A, theta) or None when the numbers do not describe an arc.
    """
    if level <= 0.0 or slope <= 0.0 or length <= 0.0:
        return None
    target = slope * length / (2.0 * level)
    lo, hi = 1e-6, np.pi / 2 - 1e-6
    if lo * np.tan(lo) > target or hi * np.tan(hi) < target:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if mid * np.tan(mid) < target:
            lo = mid
        else:
            hi = mid
    theta = 0.5 * (lo + hi)
    return level / np.cos(theta), theta


def rebuild_clipped(x, mask):
    """
    Rebuilds every clipped run. When the run looks like the top of a wave (both edges at the same
    level, slopes rising in and falling out) it is replaced by the cosine arc that matches those
    edges (exact for a sine at any frequency); otherwise by a cubic Hermite curve matching the value
    and slope on both sides. Returns float64; peaks may exceed 1.
    """
    y = np.array(x, dtype=np.float64, copy=True)
    n = y.shape[0]
    for start, stop in _runs(mask):
        a, b = start - 1, stop   # last good sample before, first good after
        if a < 0 or b >= n:
            continue             # clipped at the very edge of the file: hold the level
        ya, yb = y[a], y[b]
        sa = _edge_slope(y, a, -1)
        sb = _edge_slope(y, b, +1)
        length = float(b - a)
        sign = 1.0 if ya >= 0 else -1.0
        t = np.arange(1, stop - start + 1, dtype=np.float64)
        arc = None
        if sign * sa > 0 and sign * sb < 0 and abs(ya - yb) < 0.02 * max(abs(ya), 1e-9):
            level = 0.5 * (abs(ya) + abs(yb))
            slope = 0.5 * (abs(sa) + abs(sb))
            fit = _cosine_peak(level, slope, length)
            if fit is not None:
                amp, theta = fit
                w = 2.0 * theta / length
                arc = sign * amp * np.cos(w * (t - length / 2.0))
                arc += (yb - ya) * t / length   # tiny tilt so both ends connect exactly
        if arc is None:
            u = t / length
            h00 = 2 * u ** 3 - 3 * u ** 2 + 1
            h10 = u ** 3 - 2 * u ** 2 + u
            h01 = -2 * u ** 3 + 3 * u ** 2
            h11 = u ** 3 - u ** 2
            arc = h00 * ya + h10 * sa * length + h01 * yb + h11 * sb * length
        # The clipped region must at least reach the clipping level, so never undershoot it.
        y[start:stop] = sign * np.maximum(np.abs(arc), abs(ya))
    return y


def declip(samples, threshold=None, ceiling=0.99):
    """
    Returns (repaired, info) with info = {"samples": clipped sample count, "runs": n, "gain_db": applied}.
    The rebuilt signal is scaled so its peak sits at `ceiling`.
    """
    x = np.asarray(samples, dtype=np.float32)
    mono = x.ndim == 1
    x2 = x[:, None] if mono else x
    out = np.empty(x2.shape, dtype=np.float64)
    clipped = 0
    runs = 0
    for c in range(x2.shape[1]):
        mask = find_clipped(x2[:, c], threshold)
        clipped += int(mask.sum())
        runs += len(_runs(mask))
        out[:, c] = rebuild_clipped(x2[:, c], mask) if mask.any() else x2[:, c]
    peak = float(np.max(np.abs(out), initial=0.0))
    gain = 1.0 if peak <= ceiling or peak <= 0.0 else ceiling / peak
    out *= gain
    info = {"samples": clipped, "runs": runs, "gain_db": 20.0 * np.log10(gain) if gain > 0 else 0.0,
            "rebuilt_peak": peak}
    out = out.astype(np.float32)
    return (out[:, 0] if mono else out), info


# --------------------------------------------------------------------------- de-hum

def _tone_power(x, rate, hz):
    """Power of a mono signal at `hz` (Hann-weighted projection)."""
    n = x.shape[0]
    t = np.arange(n) / rate
    w = np.hanning(n)
    c = np.sum(x * w * np.cos(2 * np.pi * hz * t))
    s = np.sum(x * w * np.sin(2 * np.pi * hz * t))
    return (c * c + s * s) / max(np.sum(w) ** 2, 1e-12)


def _block_phasors(x, rate, hz, block, hop):
    """Complex amplitude of `hz` in each Hann block of a mono signal: [(centre_sample, phasor), ...]."""
    n = x.shape[0]
    out = []
    for start in range(-hop, n, hop):
        lo, hi = max(0, start), min(n, start + block)
        if hi - lo < block // 4:
            continue
        idx = np.arange(lo, hi)
        w = np.hanning(block)[idx - start]
        t = idx / rate
        z = np.sum(x[idx] * w * np.exp(-2j * np.pi * hz * t)) / max(np.sum(w), 1e-12) * 2.0
        out.append(((lo + hi) / 2.0, z))
    return out


def estimate_hum(x, rate, candidates=(50.0, 60.0), harmonics=4, span=1.5, step=0.05):
    """
    Picks 50 or 60 Hz (whichever carries more energy with its harmonics), refines it on a 0.05 Hz
    grid and then from the phase drift between blocks (to a few mHz).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = min(x.shape[0], int(rate * 10))
    start = (x.shape[0] - n) // 2
    seg = x[start:start + n]
    best_f, best_p = candidates[0], -1.0
    for f0 in candidates:
        p = sum(_tone_power(seg, rate, f0 * k) for k in range(1, harmonics + 1))
        if p > best_p:
            best_f, best_p = f0, p
    grid = np.arange(best_f - span, best_f + span + 1e-9, step)
    powers = [sum(_tone_power(seg, rate, f * k) for k in range(1, 3)) for f in grid]
    f = float(grid[int(np.argmax(powers))])
    # Phase-slope refinement: the phase of the fundamental across 1 s blocks drifts linearly with
    # the frequency error.
    block = int(rate)
    if seg.shape[0] >= 2 * block:
        for _ in range(2):
            ph = _block_phasors(seg, rate, f, block, block // 2)
            if len(ph) < 3:
                break
            centres = np.array([c for c, _ in ph]) / rate
            phases = np.unwrap(np.angle(np.array([z for _, z in ph])))
            slope = np.polyfit(centres, phases, 1)[0]      # rad / s
            f += slope / (2 * np.pi)
    return float(f)


def dehum(samples, rate, hz=None, harmonics=8, block_seconds=1.0):
    """
    Removes the mains hum and its harmonics by measuring each harmonic's amplitude and phase in
    overlapping Hann blocks (so slow level changes are followed) and subtracting the fitted sinusoid.
    Zero phase, no filter ringing, and the music around the hum is left alone (a block of 1 s only
    picks up what sits within about 1 Hz of each harmonic).
    hz: 50, 60 or None (auto). Returns (repaired, fundamental_hz).
    """
    x = np.asarray(samples, dtype=np.float32)
    mono = x.ndim == 1
    x2 = x[:, None] if mono else x
    f0 = estimate_hum(x2, rate) if hz is None else estimate_hum(x2, rate, candidates=(float(hz),))
    y = x2.astype(np.float64)
    n = y.shape[0]
    block = max(int(rate * block_seconds), 256)
    hop = block // 2
    t = np.arange(n) / rate
    nyq = rate / 2.0
    for k in range(1, harmonics + 1):
        f = f0 * k
        if f >= nyq * 0.95:
            break
        carrier = np.exp(2j * np.pi * f * t)
        starts = list(range(0, max(n - block, 0) + 1, hop))
        if not starts:
            starts = [0]
        for c in range(y.shape[1]):
            # One phasor per full block; the head and tail (before the first / after the last block
            # centre) reuse the nearest block's fit, which the carrier extends naturally.
            phasors = []
            for start in starts:
                lo, hi = start, min(n, start + block)
                w = np.hanning(hi - lo) if hi - lo < block else np.hanning(block)
                z = np.sum(y[lo:hi, c] * w * np.conj(carrier[lo:hi])) / max(np.sum(w), 1e-12) * 2.0
                phasors.append(z)
            fitted = np.zeros(n)
            weight = np.zeros(n)
            for start, z in zip(starts, phasors):
                lo, hi = start, min(n, start + block)
                w = np.hanning(block)[: hi - lo]
                fitted[lo:hi] += w * np.real(z * carrier[lo:hi])
                weight[lo:hi] += w
            first_centre = starts[0] + block // 2
            last_centre = starts[-1] + block // 2
            rest = np.clip(1.0 - weight, 0.0, 1.0)
            head = np.arange(n) < first_centre
            tail = np.arange(n) >= last_centre
            fitted[head] += rest[head] * np.real(phasors[0] * carrier[head])
            fitted[tail] += rest[tail] * np.real(phasors[-1] * carrier[tail])
            y[:, c] -= fitted
    out = y.astype(np.float32)
    return (out[:, 0] if mono else out), f0


# --------------------------------------------------------------------------- whole job

def _run_edges(mask, width=2):
    """Marks the `width` samples on both sides of each run boundary (the hard edges of clipping)."""
    out = np.zeros_like(mask)
    n = mask.shape[0]
    for start, stop in _runs(mask):
        out[max(0, start - width):min(n, start + width)] = True
        out[max(0, stop - width):min(n, stop + width)] = True
    return out


def repair(samples, rate, declick_on=True, declip_on=True, dehum_on=False, hum_hz=None,
           click_sensitivity=1.0, progress=None):
    """
    Runs the chosen modules in order (click, clip, hum) and returns (repaired, removed, report).
    `removed` is input - output: what you would hear with "listen to what was removed".
    """
    x = np.asarray(samples, dtype=np.float32)
    y = x
    report = {}
    steps = [m for m, on in (("declick", declick_on), ("declip", declip_on), ("dehum", dehum_on)) if on]
    protect = None
    if declick_on and declip_on:
        x2 = x[:, None] if x.ndim == 1 else x
        protect = np.stack([_run_edges(find_clipped(x2[:, c])) for c in range(x2.shape[1])], axis=1)
        protect = protect[:, 0] if x.ndim == 1 else protect
    for i, m in enumerate(steps):
        if progress:
            progress(i / max(len(steps), 1))
        if m == "declick":
            y, count = declick(y, click_sensitivity, protect)
            report["clicks"] = count
        elif m == "declip":
            y, info = declip(y)
            report["clipped_samples"] = info["samples"]
            report["clip_runs"] = info["runs"]
            report["gain_db"] = info["gain_db"]
        elif m == "dehum":
            y, f0 = dehum(y, rate, hum_hz)
            report["hum_hz"] = f0
    if progress:
        progress(1.0)
    y = np.asarray(y, dtype=np.float32)
    removed = (x - y).astype(np.float32)
    return y, removed, report


def repair_file(path, out_dir=None, declick_on=True, declip_on=True, dehum_on=False, hum_hz=None,
                click_sensitivity=1.0, write_removed=False, progress=None):
    """
    Repairs one audio file and writes "<name> - repaired.wav" (plus "<name> - removed.wav" when asked)
    next to it or into out_dir. Returns (written_paths, report).
    """
    import os

    from . import audio
    from .i18n import t

    samples, rate = audio.read(path)
    fixed, removed, report = repair(samples, rate, declick_on, declip_on, dehum_on, hum_hz,
                                    click_sensitivity, progress)
    folder, name = os.path.split(path)
    base = os.path.splitext(name)[0]
    target_dir = out_dir or folder
    os.makedirs(target_dir, exist_ok=True)
    written = []
    target = os.path.join(target_dir, "%s - %s.wav" % (base, t("repaired_label")))
    audio.write(target, fixed, rate)
    written.append(target)
    if write_removed:
        target = os.path.join(target_dir, "%s - %s.wav" % (base, t("removed_label")))
        audio.write(target, removed, rate)
        written.append(target)
    return written, report


def describe(report):
    """One line for the log / terminal, in the app language."""
    from .i18n import t

    parts = []
    if "clicks" in report:
        parts.append(t("report_clicks") % report["clicks"])
    if "clip_runs" in report:
        parts.append(t("report_clip") % (report["clip_runs"], report.get("gain_db", 0.0)))
    if "hum_hz" in report:
        parts.append(t("report_hum") % report["hum_hz"])
    return ", ".join(parts)
