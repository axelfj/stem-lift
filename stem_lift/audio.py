"""Reading songs and writing stems. Samples are float32 arrays shaped (frames, channels)."""
import os

import numpy as np
import soundfile

AUDIO_EXTENSIONS = (".wav", ".wave", ".aif", ".aiff", ".aifc", ".flac", ".mp3", ".ogg", ".opus")


class AudioError(Exception):
    pass


def is_audio_file(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def list_audio_files(folder):
    out = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if os.path.isfile(p) and is_audio_file(p):
            out.append(p)
    return out


def read(path):
    """Returns (samples, rate). Mono files come back as one channel; stems keep that count."""
    try:
        data, rate = soundfile.read(path, dtype="float32", always_2d=True)
    except (RuntimeError, soundfile.LibsndfileError) as e:
        raise AudioError("%s: %s" % (os.path.basename(path), e))
    if data.shape[0] == 0:
        raise AudioError("%s is empty" % os.path.basename(path))
    if not np.isfinite(data).all():
        raise AudioError("audio contains non-finite samples (NaN or infinity)")
    return data, int(rate)


def write(path, samples, rate, subtype="PCM_24"):
    """Writes a stem. 24-bit PCM by default; float32 if the source clips."""
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if subtype.startswith("PCM") and np.max(np.abs(x), initial=0.0) >= 1.0:
        subtype = "FLOAT"
    soundfile.write(path, x, rate, subtype=subtype)


def stem_path(source, stem_label, out_dir=None):
    """'Song.mp3' + 'Vocals' -> '<out_dir>/Song - Vocals.wav'"""
    folder, name = os.path.split(source)
    base = os.path.splitext(name)[0]
    target = out_dir or os.path.join(folder, base + " - stems")
    return os.path.join(target, "%s - %s.wav" % (base, stem_label))

