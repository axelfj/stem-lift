"""Command line: stem-lift SONG_OR_FOLDER... [--mode 2|4|6] [--out DIR] [--stems vocals,drums]"""
import argparse
import os
import sys

from . import APP_NAME, __version__
from .job import collect, run
from .separate import MODES, make_separator


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stem-lift",
                                 description="%s %s: split songs into stems." % (APP_NAME, __version__))
    ap.add_argument("paths", nargs="+", help="songs or folders")
    ap.add_argument("--mode", choices=sorted(MODES), default="4", help="number of stems (default 4)")
    ap.add_argument("--stems", help="comma-separated subset to export, e.g. vocals,drums")
    ap.add_argument("--out", metavar="DIR", help="output folder (default: '<song> - stems' next to the song)")
    ap.add_argument("--backend", choices=["demucs", "bands"], help="force a separation backend")
    ap.add_argument("--device", help="cpu, cuda or mps (default: auto)")
    ap.add_argument("--version", action="version", version=__version__)
    args = ap.parse_args(argv)

    files = collect(args.paths)
    if not files:
        print("No audio files found.", file=sys.stderr)
        return 2
    stems = args.stems.split(",") if args.stems else None
    for s in stems or []:
        if s not in MODES[args.mode]:
            print("unknown stem %r for mode %s (choose from %s)" % (s, args.mode, ", ".join(MODES[args.mode])),
                  file=sys.stderr)
            return 2

    try:
        separator = make_separator(args.backend, args.device)
    except (RuntimeError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    print("%s %s, backend: %s" % (APP_NAME, __version__, separator.name))

    def progress(n, total, path, fraction):
        sys.stdout.write("\r[%d/%d] %-40.40s %3d%%" % (n + 1, total, os.path.basename(path), fraction * 100))
        sys.stdout.flush()
        if fraction >= 1.0:
            sys.stdout.write("\n")

    failed = 0
    for path, outcome in run(files, args.mode, args.out, separator, stems, progress):
        if isinstance(outcome, Exception):
            failed += 1
            print("  ERROR %s: %s" % (os.path.basename(path), outcome))
        else:
            for p in outcome:
                print("  " + p)
    return 1 if failed else 0

