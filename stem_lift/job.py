"""One separation job: read a song, separate, write the stems. Shared by the CLI and the GUI."""
import os

from . import audio
from .i18n import t
from .separate import MODES, Cancelled, make_separator


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
    separator = separator or make_separator()
    samples, rate = audio.read(path)
    result = separator.separate(samples, rate, mode=mode, progress=progress, cancel=cancel)

    wanted = [s for s in MODES[mode] if stems is None or s in stems]
    written = []
    for name in wanted:
        target = audio.stem_path(path, stem_label(name), out_dir)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        audio.write(target, result[name], rate)
        written.append(target)
    return written


def run(files, mode="4", out_dir=None, separator=None, stems=None, progress=None, cancel=None):
    """Separates several files. progress(index, total, path, fraction). Returns [(path, stems | error)]."""
    separator = separator or make_separator()
    results = []
    for n, path in enumerate(files):
        def file_progress(fraction, n=n, path=path):
            if progress:
                progress(n, len(files), path, fraction)
        file_progress(0.0)
        try:
            results.append((path, separate_file(path, mode, out_dir, separator, stems,
                                                file_progress, cancel)))
        except Cancelled:
            raise
        except (audio.AudioError, OSError, ValueError, RuntimeError) as e:
            results.append((path, e))
    return results
