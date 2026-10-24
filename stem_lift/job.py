"""One separation job: read a song, separate, write the stems. Shared by the CLI and the GUI."""
import os
import tempfile
from collections import Counter

from . import audio
from .i18n import t
from .separate import MODES, Cancelled, make_separator, _check


def stem_label(name):
    return t("stem_" + name)


def collect(paths):
    files = []
    for p in paths:
        files += audio.list_audio_files(p) if os.path.isdir(p) else [p]
    return [f for f in files if audio.is_audio_file(f)]


def separate_file(path, mode="4", out_dir=None, separator=None, stems=None, progress=None,
                  cancel=None):
    """
    Writes one WAV per stem and returns their paths.
    stems: subset of MODES[mode] to export (default all). progress(fraction) in 0..1.
    """
    _check(cancel)
    wanted = [s for s in MODES[mode] if stems is None or s in stems]
    targets = [audio.stem_path(path, stem_label(name), out_dir) for name in wanted]
    for target in targets:
        if os.path.lexists(target):
            raise FileExistsError("output already exists: %s" % target)
    separator = separator or make_separator()
    samples, rate = audio.read(path)
    _check(cancel)
    result = separator.separate(samples, rate, mode=mode, progress=progress, cancel=cancel)
    _check(cancel)
    if not targets:
        return []
    folder = os.path.dirname(os.path.abspath(targets[0]))
    os.makedirs(folder, exist_ok=True)
    # Stage all files on the destination filesystem. Hard links publish each
    # complete file atomically and refuse to replace an existing destination.
    with tempfile.TemporaryDirectory(prefix=".stem-lift-", dir=folder) as staging:
        pending, published = [], []
        try:
            for index, (name, target) in enumerate(zip(wanted, targets)):
                _check(cancel)
                temporary = os.path.join(staging, "%d.wav" % index)
                audio.write(temporary, result[name], rate)
                pending.append((temporary, target))
            _check(cancel)
            for temporary, target in pending:
                _check(cancel)
                os.link(temporary, target)
                published.append((temporary, target))
            _check(cancel)
        except BaseException:
            # Only remove the files this job published, never an earlier stem.
            for temporary, target in published:
                if os.path.exists(target) and os.path.samefile(temporary, target):
                    os.unlink(target)
            raise
    return targets


def run(files, mode="4", out_dir=None, separator=None, stems=None, progress=None, cancel=None):
    """Separates several files. progress(index, total, path, fraction). Returns [(path, stems | error)]."""
    _check(cancel)
    files = list(files)
    wanted = [s for s in MODES[mode] if stems is None or s in stems]
    destinations = [[audio.stem_path(p, stem_label(s), out_dir) for s in wanted] for p in files]
    key = lambda p: os.path.normcase(os.path.realpath(p))
    counts = Counter(key(p) for group in destinations for p in group)
    separator = separator or make_separator()
    results = []
    for n, path in enumerate(files):
        def file_progress(fraction, n=n, path=path):
            if progress:
                progress(n, len(files), path, fraction)
        _check(cancel)
        file_progress(0.0)
        try:
            conflicts = [p for p in destinations[n] if counts[key(p)] > 1 or os.path.lexists(p)]
            if conflicts:
                raise FileExistsError("output collision: %s" % conflicts[0])
            results.append((path, separate_file(path, mode, out_dir, separator, stems,
                                                file_progress, cancel)))
        except Cancelled:
            raise
        except (audio.AudioError, OSError, ValueError, RuntimeError) as e:
            results.append((path, e))
    return results

