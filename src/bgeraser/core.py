"""Core background-removal functions."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from PIL import Image, ImageColor

PathLike = Union[str, Path]

#: Models available through rembg, smallest/fastest first.
MODELS = {
    "isnet-general-use": "Best quality — clean edges on people, products, cars (170 MB).",
    "u2net": "General purpose, good quality (170 MB).",
    "u2netp": "Fastest, small (4 MB). Rougher edges.",
    "u2net_human_seg": "Tuned for people / portraits.",
    "isnet-anime": "For anime / illustration characters.",
    "u2net_cloth_seg": "Segments clothing (upper, lower, full body).",
    "silueta": "u2net quality at ~43 MB.",
}
DEFAULT_MODEL = "isnet-general-use"

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
    solid: bool = True,
) -> Image.Image:
    """Remove the background from a PIL image and return an RGBA (or RGB) image.

    Args:
        image: Source image.
        model: One of :data:`MODELS`.
        bg_color: Optional replacement background ("white", "#00ff00", "255,0,0").
            If given, the result is flattened onto that color.
        alpha_matting: Refine edges (hair, fur). Slower.
        post_process: Apply rembg's mask post-processing (smoother mask).
        solid: Clean up the mask so the subject is never half-transparent,
            stray fragments are dropped and holes are filled (default on).
    """
    from rembg import remove  # lazy

    session = _get_session(model)
    image = image.convert("RGBA")

    if solid and not alpha_matting:
        mask = remove(image, session=session, only_mask=True, post_process_mask=post_process)
        if not isinstance(mask, Image.Image):
            mask = Image.open(io.BytesIO(mask))
        alpha = _clean_mask(mask.convert("L"))
        result = image.copy()
        result.putalpha(alpha)
    else:
        result = remove(image, session=session, alpha_matting=alpha_matting, post_process_mask=post_process)
        if not isinstance(result, Image.Image):  # very old rembg returned bytes
            result = Image.open(io.BytesIO(result))
        result = result.convert("RGBA")

    rgb = _parse_color(bg_color)
    if rgb is not None:
        background = Image.new("RGBA", result.size, rgb + (255,))
        background.alpha_composite(result)
        result = background.convert("RGB")
    return result


def _clean_mask(mask: Image.Image) -> Image.Image:
    """Turn a raw soft mask into a clean alpha channel.

    - the subject becomes fully opaque (no see-through arms or legs)
    - small disconnected fragments are removed
    - holes inside the subject are filled
    - the outline keeps a soft, slightly feathered edge with the model's
      fine detail (hair, fur) preserved in the edge zone
    """
    import cv2
    import numpy as np

    m = np.asarray(mask, dtype=np.float32) / 255.0
    solid = (m > 0.5).astype(np.uint8)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(solid)
    if n > 2:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = [i + 1 for i, a in enumerate(areas) if a >= 0.02 * areas.max()]
        solid = np.isin(labels, keep).astype(np.uint8)

    # fill enclosed holes
    flood = solid.copy()
    h, w = solid.shape
    cv2.floodFill(flood, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    solid[flood == 0] = 1

    soft = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 1.2)
    alpha = np.clip(np.maximum(soft, np.minimum(m, soft + 0.15)), 0.0, 1.0)
    alpha = np.where(soft > 0.85, 1.0, alpha)
    alpha = np.where(soft < 0.02, 0.0, alpha)
    return Image.fromarray((alpha * 255).astype(np.uint8), "L")


def get_mask(image: Image.Image, **kwargs) -> Image.Image:
    """Return only the cleaned mask (mode "L": white = keep, black = remove).

    Drop it onto a layer mask in GIMP / Photoshop / Krita to fix a cut-out by hand.
    Accepts the same options as :func:`remove_background_image` except ``bg_color``.
    """
    kwargs.pop("bg_color", None)
    rgba = remove_background_image(image, **kwargs)
    return rgba.split()[3]


def remove_background(
    input_path: PathLike,
    output_path: Optional[PathLike] = None,
    save_mask: bool = False,
    **kwargs,
) -> Path:
    """Remove the background of the image at ``input_path``.

    Writes a PNG (transparent unless ``bg_color`` is set) and returns its path.
    If ``output_path`` is omitted, ``<name>-nobg.png`` is written next to the input.
    With ``save_mask=True`` a second file ``<name>-mask.png`` (grayscale) is written
    alongside it.
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}-nobg.png")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as img:
        img.load()
        out = remove_background_image(img, **kwargs)

    if save_mask:
        if out.mode == "RGBA":
            mask = out.split()[3]
        else:  # flattened onto a color: recompute the mask
            with Image.open(input_path) as img:
                img.load()
                mask = get_mask(img, **kwargs)
        stem = output_path.stem[:-5] if output_path.stem.endswith("-nobg") else output_path.stem
        mask.save(output_path.with_name(f"{stem}-mask.png"), "PNG")

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
