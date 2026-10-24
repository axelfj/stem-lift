"""
Stem separation.

Two backends behind the same interface:
  DemucsSeparator  the real thing (Meta's Hybrid Transformer Demucs, MIT licence)
  BandSeparator    a tiny filter-bank stand-in so the app and the tests run without PyTorch

Both take (samples, rate) and return {stem_name: samples} with the same shape and rate as the
input, and the stems always sum back to the input (Demucs: within model error; bands: exactly).
"""
import os
import threading

import numpy as np

MODES = {
    "2": ("vocals", "instrumental"),
    "4": ("vocals", "drums", "bass", "other"),
    "6": ("vocals", "drums", "bass", "guitar", "piano", "other"),
}

DEMUCS_MODELS = {"2": "htdemucs", "4": "htdemucs", "6": "htdemucs_6s"}

MODEL_SAMPLE_RATE = 44100


class Cancelled(Exception):
    pass


class Separator:
    name = "base"

    def load(self, progress=None):
        """Downloads/loads the model. Called once, may take a while the first time."""

    def separate(self, samples, rate, mode="4", progress=None, cancel=None):
        raise NotImplementedError


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _to_mode(stems, mode):
    """Folds a 4- or 6-stem dict into the requested mode."""
    wanted = MODES[mode]
    if mode == "2":
        vocals = stems["vocals"]
        inst = sum(v for k, v in stems.items() if k != "vocals")
        return {"vocals": vocals, "instrumental": inst}
    return {k: stems[k] for k in wanted}


class BandSeparator(Separator):
    """Splits by frequency band with complementary crossovers. Not musical, but exact and fast."""
    name = "bands"

    def separate(self, samples, rate, mode="4", progress=None, cancel=None):
        from scipy.signal import butter, sosfilt

        x = np.asarray(samples, dtype=np.float64)
        n = x.shape[0]

        def lowpass(sig, hz):
            if hz >= rate / 2:
                return sig.copy()
            sos = butter(4, hz / (rate / 2), output="sos")
            return sosfilt(sos, sig, axis=0)

        _check(cancel)
        bass = lowpass(x, 150.0)
        rest = x - bass
        _check(cancel)
        drums = rest - lowpass(rest, 5000.0)   # the hiss and clicks
        mid = rest - drums
        _check(cancel)
        vocals = mid - lowpass(mid, 1200.0)
        other = mid - vocals
        stems = {"vocals": vocals, "drums": drums, "bass": bass, "other": other}
        if mode == "6":
            stems["guitar"] = other * 0.5
            stems["piano"] = other * 0.5
            stems["other"] = other - stems["guitar"] - stems["piano"]
        if progress:
            progress(1.0)
        out = _to_mode(stems, mode)
        return {k: v.astype(np.float32)[:n] for k, v in out.items()}


class DemucsSeparator(Separator):
    name = "demucs"

    def __init__(self, device=None, shifts=1):
        self.device = device
        self.shifts = shifts
        self._models = {}
        self._lock = threading.Lock()

    @staticmethod
    def pick_device():
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load(self, progress=None, mode="4"):
        from demucs.pretrained import get_model

        name = DEMUCS_MODELS[mode]
        with self._lock:
            if name in self._models:
                return self._models[name]
            if self.device is None:
                self.device = self.pick_device()
            model = get_model(name)
            model.to(self.device)
            model.eval()
            self._models[name] = model
            return model

    def separate(self, samples, rate, mode="4", progress=None, cancel=None):
        import torch
        from demucs.apply import apply_model
        from demucs.audio import convert_audio

        model = self.load(mode=mode)
        _check(cancel)

        x = np.asarray(samples, dtype=np.float32)
        wav = torch.from_numpy(x.T.copy())  # (channels, frames)
        wav = convert_audio(wav, rate, model.samplerate, model.audio_channels)
        ref = wav.mean(0)
        mean, std = ref.mean(), ref.std() + 1e-8
        wav = (wav - mean) / std

        length = wav.shape[-1]

        def on_chunk(info):
            # Called by Demucs when each 8-second chunk starts/ends; raising here aborts the run.
            _check(cancel)
            if progress and info.get("state") == "end":
                done = (info.get("segment_offset", 0) + 1) / max(1, length)
                shifts = max(1, self.shifts)
                done = (info.get("shift_idx", 0) + done) / shifts
                progress(min(0.99, float(done)))

        with torch.no_grad():
            sources = apply_model(model, wav[None], device=self.device, shifts=self.shifts,
                                  split=True, overlap=0.25, progress=False, callback=on_chunk)[0]
        sources = sources * std + mean

        stems = {}
        for name, src in zip(model.sources, sources):
            src = convert_audio(src, model.samplerate, rate, x.shape[1])
            y = src.cpu().numpy().T
            # Resampling can be a sample off; match the input length exactly.
            if y.shape[0] < x.shape[0]:
                y = np.pad(y, ((0, x.shape[0] - y.shape[0]), (0, 0)))
            stems[name] = y[: x.shape[0]].astype(np.float32)
        if progress:
            progress(1.0)
        return _to_mode(stems, mode)


def make_separator(backend=None, device=None):
    """Demucs is required by default; the frequency-band test backend is opt-in."""
    backend = backend or os.environ.get("STEM_LIFT_BACKEND") or "demucs"
    if backend == "bands":
        return BandSeparator()
    if backend != "demucs":
        raise ValueError("unknown separation backend: %s" % backend)
    try:
        import demucs  # noqa: F401
        import torch  # noqa: F401
    except ImportError as e:
        raise RuntimeError("Demucs is required for instrument separation. "
                           "Install stem-lift[demucs] or use the desktop installer. "
                           "The bands backend is only a frequency-split test tool.") from e
    return DemucsSeparator(device=device)
