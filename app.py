"""
Entry point for the packaged app and for running from source.

  python app.py              opens the window
  python app.py SONG...      command line (see --help)
  python app.py repair FILE  Repair Ready from the command line (de-click, de-clip, de-hum)
  python app.py --selftest   checks a packaged build without opening a window or a model download
"""
import sys


def selftest():
    import os
    import tempfile

    import numpy as np
    import tkinter  # noqa: F401  (the window needs it in the bundle)

    from stem_lift import audio
    from stem_lift.job import separate_file
    from stem_lift.separate import BandSeparator

    rate = 44100
    t = np.arange(rate * 3) / rate
    song = np.stack([0.3 * np.sin(2 * np.pi * 110 * t) + 0.2 * np.sin(2 * np.pi * 2000 * t)] * 2, 1)
    folder = tempfile.mkdtemp()
    wav = os.path.join(folder, "selftest.wav")
    audio.write(wav, song, rate)
    paths = separate_file(wav, "4", separator=BandSeparator())
    assert len(paths) == 4, paths
    total = sum(audio.read(p)[0] for p in paths)
    assert np.max(np.abs(total - song)) < 1e-3
    # The packaged build must also carry PyTorch and the Demucs code (not the weights).
    import demucs.pretrained  # noqa: F401
    import torch  # noqa: F401
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        selftest()
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]
    if args and args[0] == "repair":
        from stem_lift.repair_cli import main as repair_main
        return repair_main(args[1:])
    if args:
        from stem_lift.cli import main as cli_main
        return cli_main(args)
    from stem_lift.gui import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
