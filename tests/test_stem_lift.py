"""Tests that run without PyTorch: the band backend, file handling and the CLI."""
import os
import shutil
import tempfile
import threading
import unittest

import numpy as np

from stem_lift import audio, cli
from stem_lift.job import collect, run, separate_file
from stem_lift.separate import MODES, BandSeparator, Cancelled, make_separator

RATE = 44100


def song(seconds=2.0, rate=RATE, channels=2):
    t = np.arange(int(rate * seconds)) / rate
    x = (0.3 * np.sin(2 * np.pi * 55 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)
         + 0.1 * np.sin(2 * np.pi * 3000 * t) + 0.05 * np.sin(2 * np.pi * 9000 * t))
    return np.stack([x] * channels, 1).astype(np.float32)


class BandSeparatorTest(unittest.TestCase):
    def test_stems_sum_to_input_in_every_mode(self):
        x = song()
        for mode, names in MODES.items():
            stems = BandSeparator().separate(x, RATE, mode)
            self.assertEqual(tuple(stems), names)
            for s in stems.values():
                self.assertEqual(s.shape, x.shape)
                self.assertEqual(s.dtype, np.float32)
            total = sum(stems.values())
            self.assertLess(np.max(np.abs(total - x)), 1e-5)

    def test_bass_stem_holds_the_low_end(self):
        x = song()
        stems = BandSeparator().separate(x, RATE, "4")
        spectrum = np.abs(np.fft.rfft(stems["bass"][:, 0]))
        freqs = np.fft.rfftfreq(x.shape[0], 1 / RATE)
        low = spectrum[(freqs > 40) & (freqs < 70)].max()
        high = spectrum[freqs > 400].max()
        self.assertGreater(low / high, 100)

    def test_cancel_raises(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            BandSeparator().separate(song(), RATE, "4", cancel=cancel)

    def test_mono_input_keeps_one_channel(self):
        stems = BandSeparator().separate(song(channels=1), RATE, "2")
        self.assertEqual(stems["vocals"].shape[1], 1)


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.wav = os.path.join(self.folder, "My Song.wav")
        self.x = song()
        audio.write(self.wav, self.x, RATE)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_separate_file_writes_named_24bit_stems_next_to_the_song(self):
        paths = separate_file(self.wav, "4", separator=BandSeparator())
        self.assertEqual(len(paths), 4)
        self.assertTrue(all(os.path.dirname(p) == os.path.join(self.folder, "My Song - stems") for p in paths))
        self.assertTrue(any(p.endswith("My Song - Vocals.wav") or p.endswith("My Song - Voz.wav") for p in paths))
        import soundfile
        for p in paths:
            info = soundfile.info(p)
            self.assertEqual(info.samplerate, RATE)
            self.assertEqual(info.frames, self.x.shape[0])
            self.assertEqual(info.channels, 2)
            self.assertEqual(info.subtype, "PCM_24")
        total = sum(audio.read(p)[0] for p in paths)
        self.assertLess(np.max(np.abs(total - self.x)), 1e-3)  # 24-bit quantisation

    def test_subset_and_custom_output_folder(self):
        out = os.path.join(self.folder, "out")
        paths = separate_file(self.wav, "2", out_dir=out, separator=BandSeparator(), stems=["vocals"])
        self.assertEqual(len(paths), 1)
        self.assertEqual(os.path.dirname(paths[0]), out)

    def test_hot_source_is_written_as_float(self):
        hot = os.path.join(self.folder, "hot.wav")
        audio.write(hot, self.x * 4.0, RATE, subtype="FLOAT")
        paths = separate_file(hot, "4", separator=BandSeparator())
        import soundfile
        self.assertTrue(any(soundfile.info(p).subtype == "FLOAT" for p in paths))

    def test_run_reports_errors_per_file(self):
        bad = os.path.join(self.folder, "broken.wav")
        with open(bad, "wb") as f:
            f.write(b"RIFF not really a wav")
        results = run([self.wav, bad], "4", separator=BandSeparator())
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0][1], list)
        self.assertIsInstance(results[1][1], Exception)

    def test_collect_folder_skips_non_audio(self):
        with open(os.path.join(self.folder, "notes.txt"), "w") as f:
            f.write("x")
        self.assertEqual(collect([self.folder]), [self.wav])

    def test_cli_runs_with_band_backend(self):
        out = os.path.join(self.folder, "cli")
        code = cli.main([self.wav, "--backend", "bands", "--mode", "2", "--out", out])
        self.assertEqual(code, 0)
        self.assertEqual(len(os.listdir(out)), 2)

    def test_cli_rejects_unknown_stem(self):
        self.assertEqual(cli.main([self.wav, "--backend", "bands", "--stems", "piano"]), 2)


class FactoryTest(unittest.TestCase):
    def test_bands_backend_is_selectable(self):
        self.assertEqual(make_separator("bands").name, "bands")

    def test_env_override(self):
        os.environ["STEM_LIFT_BACKEND"] = "bands"
        try:
            self.assertEqual(make_separator().name, "bands")
        finally:
            del os.environ["STEM_LIFT_BACKEND"]


if __name__ == "__main__":
    unittest.main()
