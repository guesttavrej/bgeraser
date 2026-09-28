"""Core background-removal functions."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from PIL import Image, ImageColor

PathLike = Union[str, Path]

#: Models available through rembg, smallest/fastest first.
MODELS = {
    "u2netp": "Fast, small (4 MB). Good default for quick jobs.",
    "u2net": "General purpose, higher quality (170 MB).",
    "u2net_human_seg": "Tuned for people / portraits.",
    "u2net_cloth_seg": "Segments clothing (upper, lower, full body).",
    "isnet-general-use": "Newer general model, often best edges.",
    "isnet-anime": "For anime / illustration characters.",
    "silueta": "u2net quality at ~43 MB.",
    "sam": "Segment Anything (needs prompts, advanced).",
}
DEFAULT_MODEL = "u2netp"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

_sessions: dict = {}


def _get_session(model: str):
    """Load (and cache) a rembg model session."""
    if model not in MODELS:
        raise ValueError(f"Unknown model '{model}'. Choose from: {', '.join(MODELS)}")
    if model not in _sessions:
        from rembg import new_session  # imported lazily: slow import

        _sessions[model] = new_session(model)
    return _sessions[model]


def _parse_color(color: Optional[str]):
    """'#ffffff', 'white', '255,0,0' or None -> RGB tuple or None."""
    if not color:
        return None
    color = color.strip()
    if "," in color:
        parts = [int(p) for p in color.split(",")]
        return tuple(parts[:3])
    return ImageColor.getrgb(color)


def remove_background_image(
    image: Image.Image,
    *,
    model: str = DEFAULT_MODEL,
    bg_color: Optional[str] = None,
    alpha_matting: bool = False,
    post_process: bool = False,
) -> Image.Image:
    """Remove the background from a PIL image and return an RGBA (or RGB) image.

    Args:
        image: Source image.
        model: One of :data:`MODELS`.
        bg_color: Optional replacement background ("white", "#00ff00", "255,0,0").
            If given, the result is flattened onto that color.
        alpha_matting: Refine edges (hair, fur). Slower.
        post_process: Apply rembg's mask post-processing (smoother mask).
    """
    from rembg import remove  # lazy

    session = _get_session(model)
    result = remove(
        image,
        session=session,
        alpha_matting=alpha_matting,
        post_process_mask=post_process,
    )
    if not isinstance(result, Image.Image):  # very old rembg returned bytes
        result = Image.open(io.BytesIO(result))
    result = result.convert("RGBA")

    rgb = _parse_color(bg_color)
    if rgb is not None:
        background = Image.new("RGBA", result.size, rgb + (255,))
        background.alpha_composite(result)
        result = background.convert("RGB")
    return result


def remove_background(
    input_path: PathLike,
    output_path: Optional[PathLike] = None,
    **kwargs,
) -> Path:
    """Remove the background of the image at ``input_path``.

    Writes a PNG (transparent unless ``bg_color`` is set) and returns its path.
    If ``output_path`` is omitted, ``<name>-nobg.png`` is written next to the input.
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}-nobg.png")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as img:
        img.load()
        out = remove_background_image(img, **kwargs)

    fmt = "PNG"
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        fmt = "JPEG"
        if out.mode == "RGBA":  # JPEG cannot hold transparency
            flat = Image.new("RGB", out.size, (255, 255, 255))
            flat.paste(out, mask=out.split()[3])
            out = flat
    elif output_path.suffix.lower() == ".webp":
        fmt = "WEBP"
    out.save(output_path, fmt)
    return output_path


def remove_background_bytes(data: bytes, **kwargs) -> bytes:
    """Same as :func:`remove_background` but in-memory. Returns PNG bytes."""
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        out = remove_background_image(img, **kwargs)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def iter_images(folder: PathLike, recursive: bool = False) -> Iterable[Path]:
    folder = Path(folder)
    pattern = "**/*" if recursive else "*"
    for p in sorted(folder.glob(pattern)):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and not p.stem.endswith("-nobg"):
            yield p


def process_folder(
    input_dir: PathLike,
    output_dir: Optional[PathLike] = None,
    *,
    recursive: bool = False,
    on_progress: Optional[Callable[[Path, Path], None]] = None,
    **kwargs,
) -> list[Path]:
    """Remove backgrounds from every image in a folder. Returns output paths."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else input_dir / "nobg"
    written: list[Path] = []
    for src in iter_images(input_dir, recursive=recursive):
        rel = src.relative_to(input_dir)
        dst = (output_dir / rel).with_suffix(".png")
        remove_background(src, dst, **kwargs)
        written.append(dst)
        if on_progress:
            on_progress(src, dst)
    return written
