# bgeraser

**Remove image backgrounds on your own computer.** No uploads, no API keys, no watermarks, no limits.

Works three ways:

| | |
|---|---|
| **Command line** | `bgeraser photo.jpg` → `photo-nobg.png` |
| **Python library** | `remove_background("photo.jpg")` |
| **Local web page** | `bgeraser serve` → drag & drop in your browser |

Powered by open-source [U²-Net](https://github.com/xuebinqin/U-2-Net) / ISNet models through [rembg](https://github.com/danielgatis/rembg).

## Install

```bash
pip install bgeraser            # CLI + library
pip install "bgeraser[web]"     # also the drag & drop web page
```

Needs Python 3.9+. The first run downloads the model (4 MB for the default `u2netp`; larger models download when you choose them).

## Command line

```bash
# one image → transparent PNG next to it
bgeraser photo.jpg

# choose the output name
bgeraser photo.jpg -o clean.png

# solid background instead of transparent (product photos, ID photos)
bgeraser photo.jpg --bg white
bgeraser photo.jpg --bg "#00ff00"

# a whole folder → ./products/nobg/
bgeraser ./products
bgeraser ./products -o ./out --recursive

# better model for people
bgeraser --model u2net_human_seg me.png

# finer edges for hair / fur (slower)
bgeraser photo.jpg --matting

# list models
bgeraser models
```

## Web page (drag & drop)

```bash
bgeraser serve
```

Then open <http://127.0.0.1:5000>. Drop, paste, or pick an image; download the PNG. Everything stays on your machine.

`bgeraser serve --port 8080 --model isnet-general-use` to change port or model.

## Python

```python
from bgeraser import remove_background, remove_background_bytes, process_folder

remove_background("photo.jpg")                           # -> photo-nobg.png
remove_background("photo.jpg", "out.png", bg_color="white")
remove_background("photo.jpg", model="isnet-general-use", alpha_matting=True)

png_bytes = remove_background_bytes(open("photo.jpg", "rb").read())   # in-memory

process_folder("./products", "./products/out")           # batch
```

## Models

| name | best for |
|---|---|
| `u2netp` *(default)* | fast, small, everyday use |
| `u2net` | general, higher quality |
| `isnet-general-use` | often the cleanest edges |
| `u2net_human_seg` | people / portraits |
| `isnet-anime` | anime & illustrations |
| `u2net_cloth_seg` | clothing segmentation |
| `silueta` | u2net quality, smaller file |

## Why

Online background removers are slow, watermark the result, charge per image, or make you upload customer photos to a stranger's server. This does the same job offline, for free, in one command.

## Contributing

Issues and pull requests welcome. Run tests with:

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT © Tavrej / Yonzon Studio
