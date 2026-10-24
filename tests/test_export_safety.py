import builtins
import os
import threading
from unittest.mock import patch

import numpy as np
import pytest

from stem_lift import audio, job
from stem_lift.separate import BandSeparator, Cancelled, make_separator


def source(tmp_path, name='Song.wav'):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    audio.write(str(path), np.ones((4410, 2), dtype=np.float32) * .1, 44100)
    return str(path)


def test_missing_demucs_never_falls_back():
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name in ('demucs', 'torch'):
            raise ImportError(name)
        return original(name, *args, **kwargs)
    with patch.dict(os.environ, {}, clear=True), patch('builtins.__import__', side_effect=missing):
        with pytest.raises(RuntimeError, match='Demucs is required'):
            make_separator()
    with pytest.raises(ValueError, match='unknown'):
        make_separator('typo')


def test_batch_detects_same_basename_before_export(tmp_path):
    a, b = source(tmp_path, 'one/Song.wav'), source(tmp_path, 'two/Song.wav')
    out = str(tmp_path / 'output')
    separator = BandSeparator()
    with patch.object(separator, 'separate', wraps=separator.separate) as separate:
        results = job.run([a, b], out_dir=out, separator=separator)
        assert separate.call_count == 0
    assert all(isinstance(outcome, FileExistsError) for _, outcome in results)
    assert not os.path.exists(out)


def test_existing_export_is_never_replaced(tmp_path):
    path = source(tmp_path)
    outputs = job.separate_file(path, separator=BandSeparator())
    before = {p: open(p, 'rb').read() for p in outputs}
    with pytest.raises(FileExistsError):
        job.separate_file(path, separator=BandSeparator())
    assert all(open(p, 'rb').read() == data for p, data in before.items())


@pytest.mark.parametrize('when', ['after_inference', 'during_write', 'during_publish'])
def test_cancel_rolls_back_only_own_outputs(tmp_path, when):
    path = source(tmp_path)
    out = tmp_path / 'out'
    out.mkdir()
    previous = out / 'previous.wav'
    previous.write_bytes(b'existing result')
    event = threading.Event()
    class CancellingSeparator(BandSeparator):
        def separate(self, *args, **kwargs):
            result = super().separate(*args, **kwargs)
            if when == 'after_inference':
                event.set()
            return result
    write, link = audio.write, os.link
    def cancel_write(*args, **kwargs):
        write(*args, **kwargs)
        if when == 'during_write':
            event.set()
    def cancel_publish(*args, **kwargs):
        link(*args, **kwargs)
        if when == 'during_publish':
            event.set()
    with patch.object(audio, 'write', side_effect=cancel_write), patch.object(os, 'link', side_effect=cancel_publish):
        with pytest.raises(Cancelled):
            job.separate_file(path, out_dir=str(out), separator=CancellingSeparator(), cancel=event)
    assert list(out.iterdir()) == [previous]
    assert previous.read_bytes() == b'existing result'


def test_publication_race_does_not_replace_other_writer(tmp_path):
    path = source(tmp_path)
    out = tmp_path / 'out'
    link = os.link
    def competing_writer(src, dst):
        if not os.path.exists(dst):
            with open(dst, 'wb') as f:
                f.write(b'other writer')
        link(src, dst)
    with patch.object(os, 'link', side_effect=competing_writer):
        with pytest.raises(FileExistsError):
            job.separate_file(path, out_dir=str(out), separator=BandSeparator())
    assert len(list(out.iterdir())) == 1
    assert next(out.iterdir()).read_bytes() == b'other writer'
