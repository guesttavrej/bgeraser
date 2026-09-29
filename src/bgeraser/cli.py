"""Command-line interface for bgeraser."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .core import DEFAULT_MODEL, MODELS, process_folder, remove_background


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bgeraser",
        description="Remove image backgrounds locally. Works on a single file or a whole folder.",
        epilog=(
            "examples:\n"
            "  bgeraser photo.jpg                     -> photo-nobg.png\n"
            "  bgeraser photo.jpg -o clean.png\n"
            "  bgeraser photo.jpg --bg white          -> white background instead of transparent\n"
            "  bgeraser ./products -o ./products/out  -> every image in the folder\n"
            "  bgeraser photo.jpg --mask               -> also writes photo-mask.png for GIMP\n"
            "  bgeraser serve                         -> open a local web page (drag & drop)\n"
            "  bgeraser models                        -> list available models"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", nargs="?", help="image file or folder, or 'serve' / 'models'")
    p.add_argument("-o", "--output", help="output file (single image) or output folder")
    p.add_argument(
        "-m", "--model", default=DEFAULT_MODEL, choices=list(MODELS),
        help=f"segmentation model (default: {DEFAULT_MODEL})",
    )
    p.add_argument("--bg", metavar="COLOR", help="replace background with a color, e.g. white, #00ff00, 255,0,0")
    p.add_argument("--matting", action="store_true", help="alpha matting for finer edges (hair, fur). Slower")
    p.add_argument("--post", action="store_true", help="post-process the mask for smoother results")
    p.add_argument("--mask", action="store_true", help="also save the mask as <name>-mask.png (for GIMP / Photoshop layer masks)")
    p.add_argument("-r", "--recursive", action="store_true", help="include sub-folders when input is a folder")
    p.add_argument("--host", default="127.0.0.1", help="host for 'serve' (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=5000, help="port for 'serve' (default 5000)")
    p.add_argument("-q", "--quiet", action="store_true", help="no progress output")
    p.add_argument("-V", "--version", action="version", version=f"bgeraser {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.input:
        parser.print_help()
        return 1

    if args.input == "models":
        for name, desc in MODELS.items():
            mark = " (default)" if name == DEFAULT_MODEL else ""
            print(f"{name:18s} {desc}{mark}")
        return 0

    if args.input == "serve":
        from .web import serve

        serve(host=args.host, port=args.port, model=args.model)
        return 0

    opts = dict(
        model=args.model,
        bg_color=args.bg,
        alpha_matting=args.matting,
        post_process=args.post,
    )
    src = Path(args.input)
    if not src.exists():
        print(f"error: {src} does not exist", file=sys.stderr)
        return 2

    t0 = time.time()
    if src.is_dir():
        def progress(i, o):
            if not args.quiet:
                print(f"  {i.name} -> {o}")

        written = process_folder(src, args.output, recursive=args.recursive, on_progress=progress, save_mask=args.mask, **opts)
        if not written:
            print("no images found", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"done: {len(written)} image(s) in {time.time() - t0:.1f}s")
        return 0

    out = remove_background(src, args.output, save_mask=args.mask, **opts)
    if not args.quiet:
        print(f"{src.name} -> {out}  ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
