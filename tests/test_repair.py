"""Repair Ready tests: de-click, de-clip and de-hum on synthetic signals (no model, no GUI)."""
import unittest

import numpy as np

from stem_lift import repair

RATE = 44100


def sine(hz, seconds=2.0, amp=0.5, rate=RATE):
    t = np.arange(int(rate * seconds)) / rate
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def db(a, b):
    return 20.0 * np.log10(np.sqrt(np.mean(a ** 2)) / max(np.sqrt(np.mean(b ** 2)), 1e-12))


class DeclickTest(unittest.TestCase):
    def test_fifty_clicks_on_a_sine_leave_a_residue_under_minus_40_db(self):
        clean = sine(440.0)
        rng = np.random.default_rng(3)
        dirty = clean.copy()
        positions = rng.integers(1000, clean.shape[0] - 1000, 50)
        for p in positions:
            width = int(rng.integers(1, 6))
            dirty[p:p + width] += rng.uniform(0.2, 0.8) * rng.choice([-1, 1])
        fixed, count = repair.declick(dirty)
        self.assertGreaterEqual(count, 45)
        self.assertLessEqual(count, 55)
        residue = fixed - clean
        self.assertLess(db(residue, clean), -40.0)
        # Where there were no clicks nothing changed.
        mask = np.ones(clean.shape[0], dtype=bool)
        for p in positions:
            mask[p - 4:p + 10] = False
        self.assertTrue(np.array_equal(fixed[mask], dirty[mask]))

    def test_a_clean_signal_is_untouched(self):
        clean = sine(1000.0) + sine(3300.0, amp=0.2)
        fixed, count = repair.declick(clean)
        self.assertEqual(count, 0)
        self.assertTrue(np.array_equal(fixed, clean))

    def test_stereo_channels_are_handled_independently(self):
        clean = np.stack([sine(220.0), sine(330.0)], 1)
        dirty = clean.copy()
        dirty[5000:5003, 1] += 0.7
        fixed, count = repair.declick(dirty)
        self.assertEqual(count, 1)
        self.assertTrue(np.array_equal(fixed[:, 0], dirty[:, 0]))
        self.assertLess(db(fixed[:, 1] - clean[:, 1], clean[:, 1]), -40.0)


class DeclipTest(unittest.TestCase):
    def test_a_sine_clipped_at_half_recovers_its_peak_within_5_percent(self):
        for hz in (100.0, 440.0, 1000.0):
            clean = sine(hz, amp=1.0)
            clipped = np.clip(clean, -0.5, 0.5)
            fixed, info = repair.declip(clipped)
            self.assertGreater(info["runs"], 10)
            # Peak before the safety gain: within 5 % of the original 1.0.
            self.assertLess(abs(info["rebuilt_peak"] - 1.0), 0.05, msg="%.0f Hz: %.3f" % (hz, info["rebuilt_peak"]))
            # The output never exceeds 0.99 and keeps the shape: correlation with the original > 0.999.
            self.assertLessEqual(float(np.max(np.abs(fixed))), 0.99 + 1e-6)
            self.assertGreater(float(np.max(np.abs(fixed))), 0.9)
            corr = np.corrcoef(fixed, clean)[0, 1]
            self.assertGreater(corr, 0.999, msg="%.0f Hz" % hz)

    def test_an_unclipped_signal_passes_unchanged(self):
        clean = sine(300.0, amp=0.7)
        fixed, info = repair.declip(clean)
        self.assertEqual(info["runs"], 0)
        self.assertEqual(info["gain_db"], 0.0)
        self.assertTrue(np.array_equal(fixed, clean))


class DehumTest(unittest.TestCase):
    def test_60_hz_hum_with_three_harmonics_drops_at_least_30_db(self):
        music = sine(440.0, amp=0.3) + sine(1234.0, amp=0.1)
        hum = sum(sine(60.0 * k, amp=0.1 / k) for k in range(1, 5))
        fixed, f0 = repair.dehum(music + hum, RATE, hz=None)
        self.assertAlmostEqual(f0, 60.0, delta=0.1)
        # Hum left vs hum before, measured as the residual against the clean music.
        residue = fixed - music
        self.assertLess(db(residue, hum), -30.0)
        # The music itself is essentially intact (the notches are 1 Hz wide).
        self.assertLess(db(residue, music), -20.0)

    def test_auto_picks_50_hz_and_refines_a_drift(self):
        music = sine(880.0, amp=0.2)
        hum = sum(sine(50.4 * k, amp=0.1 / k) for k in range(1, 4))
        fixed, f0 = repair.dehum(music + hum, RATE)
        self.assertAlmostEqual(f0, 50.4, delta=0.1)
        self.assertLess(db(fixed - music, hum), -25.0)


class RepairJobTest(unittest.TestCase):
    def test_repair_returns_what_was_removed(self):
        clean = sine(440.0, amp=1.0)
        dirty = np.clip(clean, -0.6, 0.6)
        dirty[20000:20002] += 0.5
        fixed, removed, report = repair.repair(dirty, RATE, declick_on=True, declip_on=True, dehum_on=False)
        self.assertEqual(fixed.dtype, np.float32)
        self.assertTrue(np.allclose(dirty - fixed, removed, atol=1e-6))
        self.assertGreaterEqual(report["clicks"], 1)
        self.assertGreater(report["clip_runs"], 100)
        self.assertLessEqual(report["gain_db"], 0.0)
        # The rebuilt peaks rise well above the 0.6 clipping level.
        self.assertGreater(float(np.max(np.abs(fixed))), 0.85)


class RepairFileTest(unittest.TestCase):
    def test_repair_file_and_cli_write_the_repaired_and_removed_files(self):
        import os
        import shutil
        import tempfile

        from stem_lift import audio
        from stem_lift.repair_cli import main as cli_main

        folder = tempfile.mkdtemp()
        try:
            clean = sine(440.0, amp=1.0)
            # A real recording picks up the hum before the converter clips, so the hum is clipped too.
            hum = sum(sine(60.0 * k, amp=0.05) for k in range(1, 4))
            dirty = np.clip(clean + hum, -0.5, 0.5)
            path = os.path.join(folder, "toma.wav")
            audio.write(path, dirty, RATE, subtype="FLOAT")
            written, report = repair.repair_file(path, dehum_on=True, write_removed=True)
            self.assertEqual(len(written), 2)
            for w in written:
                self.assertTrue(os.path.exists(w), w)
            fixed, rate = audio.read(written[0])
            self.assertEqual(rate, RATE)
            self.assertGreater(float(np.max(np.abs(fixed))), 0.9)
            self.assertAlmostEqual(report["hum_hz"], 60.0, delta=0.1)
            self.assertIn("Hz", repair.describe(report))
            out = os.path.join(folder, "out")
            self.assertEqual(cli_main([path, "--dehum", "60", "--out", out]), 0)
            self.assertEqual(len(os.listdir(out)), 1)
        finally:
            shutil.rmtree(folder)


if __name__ == "__main__":
    unittest.main()
