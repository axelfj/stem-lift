"""Command line: stem-lift-repair FILE_OR_FOLDER... [--no-declick] [--no-declip] [--dehum auto|50|60] [--removed] [--out DIR]"""
import argparse
import os
import sys

from . import APP_NAME, __version__
from .job import collect
from .repair import describe, repair_file


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stem-lift-repair",
                                 description="%s %s, Repair Ready: de-click, de-clip and de-hum." % (APP_NAME, __version__))
    ap.add_argument("paths", nargs="+", help="audio files or folders")
    ap.add_argument("--no-declick", action="store_true", help="skip click / pop removal")
    ap.add_argument("--no-declip", action="store_true", help="skip clipped-peak reconstruction")
    ap.add_argument("--dehum", choices=["auto", "50", "60"], help="remove mains hum (auto picks 50 or 60 Hz)")
    ap.add_argument("--sensitivity", type=float, default=1.0, help="click sensitivity 0.5 .. 2 (default 1)")
    ap.add_argument("--removed", action="store_true", help="also write '<name> - removed.wav' (what was taken out)")
    ap.add_argument("--out", metavar="DIR", help="output folder (default: next to each file)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    files = collect(args.paths)
    if not files:
        print("No audio files found.", file=sys.stderr)
        return 2
    hum_hz = None if args.dehum in (None, "auto") else float(args.dehum)
    failures = 0
    for n, path in enumerate(files):
        sys.stdout.write("[%d/%d] %s ... " % (n + 1, len(files), os.path.basename(path)))
        sys.stdout.flush()
        try:
            written, report = repair_file(path, args.out, not args.no_declick, not args.no_declip,
                                          args.dehum is not None, hum_hz, args.sensitivity, args.removed)
        except Exception as e:  # reported per file, the batch goes on
            failures += 1
            print("error: %s" % e)
            continue
        print(describe(report))
        for w in written:
            print("    " + w)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
