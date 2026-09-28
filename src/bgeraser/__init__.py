"""bgeraser — remove image backgrounds locally.

    >>> from bgeraser import remove_background
    >>> remove_background("photo.jpg", "photo-nobg.png")

Everything runs on your machine using open-source U²-Net / ISNet models
via rembg. Nothing is uploaded anywhere.
"""

from .core import (
    MODELS,
    DEFAULT_MODEL,
    remove_background,
    remove_background_bytes,
    process_folder,
)

__version__ = "0.1.0"
__all__ = [
    "MODELS",
    "DEFAULT_MODEL",
    "remove_background",
    "remove_background_bytes",
    "process_folder",
    "__version__",
]
