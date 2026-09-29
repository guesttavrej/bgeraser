import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from bgeraser import remove_background, remove_background_bytes, process_folder, MODELS, DEFAULT_MODEL
from bgeraser.cli import main


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    """Red circle on a white background — an easy subject for the model."""
    img = Image.new("RGB", (160, 160), "white")
    ImageDraw.Draw(img).ellipse((30, 30, 130, 130), fill=(220, 30, 30))
    p = tmp_path / "circle.jpg"
    img.save(p, quality=95)
    return p


def test_default_model_listed():
    assert DEFAULT_MODEL in MODELS


def test_remove_creates_transparent_png(sample: Path):
    out = remove_background(sample)
    assert out.name == "circle-nobg.png"
    with Image.open(out) as im:
        assert im.mode == "RGBA"
        assert im.size == (160, 160)
        alpha = im.split()[3]
        assert alpha.getpixel((2, 2)) < 40          # corner should be (mostly) transparent
        assert alpha.getpixel((80, 80)) > 200       # centre of circle should be opaque


def test_bg_color_flattens(sample: Path, tmp_path: Path):
    out = remove_background(sample, tmp_path / "flat.png", bg_color="#00ff00")
    with Image.open(out) as im:
        assert im.mode == "RGB"
        assert im.getpixel((2, 2)) == (0, 255, 0)


def test_bytes_roundtrip(sample: Path):
    png = remove_background_bytes(sample.read_bytes())
    with Image.open(io.BytesIO(png)) as im:
        assert im.format == "PNG" and im.mode == "RGBA"


def test_unknown_model(sample: Path):
    with pytest.raises(ValueError):
        remove_background(sample, model="does-not-exist")


def test_process_folder(sample: Path, tmp_path: Path):
    (tmp_path / "second.png").write_bytes(sample.read_bytes())
    written = process_folder(tmp_path, tmp_path / "out")
    assert sorted(p.name for p in written) == ["circle.png", "second.png"]
    assert all(p.exists() for p in written)


def test_cli_single(sample: Path, tmp_path: Path, capsys):
    rc = main([str(sample), "-o", str(tmp_path / "cli.png"), "-q"])
    assert rc == 0 and (tmp_path / "cli.png").exists()


def test_cli_models(capsys):
    assert main(["models"]) == 0
    assert DEFAULT_MODEL in capsys.readouterr().out


def test_cli_missing_file(tmp_path: Path):
    assert main([str(tmp_path / "nope.jpg")]) == 2


def test_web_app(sample: Path):
    flask = pytest.importorskip("flask")
    from bgeraser.web import create_app

    client = create_app().test_client()
    assert client.get("/health").json["ok"] is True
    assert b"bgeraser" in client.get("/").data
    r = client.post("/remove", data={"image": (io.BytesIO(sample.read_bytes()), "circle.jpg")})
    assert r.status_code == 200 and r.mimetype == "image/png"
    assert client.post("/remove", data={}).status_code == 400


def test_save_mask(sample: Path, tmp_path: Path):
    from bgeraser import get_mask

    out = remove_background(sample, tmp_path / "x-nobg.png", save_mask=True)
    mask_path = tmp_path / "x-mask.png"
    assert out.exists() and mask_path.exists()
    with Image.open(mask_path) as m:
        assert m.mode == "L" and m.size == (160, 160)
        assert m.getpixel((80, 80)) > 200 and m.getpixel((2, 2)) < 40
    with Image.open(sample) as im:
        assert get_mask(im).mode == "L"


def test_cli_mask_flag(sample: Path, tmp_path: Path):
    assert main([str(sample), "-o", str(tmp_path / "y.png"), "--mask", "-q"]) == 0
    assert (tmp_path / "y-mask.png").exists()
