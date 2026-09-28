"""Local web UI: `bgeraser serve` then open http://127.0.0.1:5000."""

from __future__ import annotations

import io
import threading
from pathlib import Path

from .core import DEFAULT_MODEL, MODELS, remove_background_bytes

HERE = Path(__file__).parent
TEMPLATE = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
SAMPLES_DIR = HERE / "samples"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Samples shown on the home page: (file stem, label shown in the tab)
SAMPLE_CATEGORIES = [
    ("product", "Products"),
    ("people", "People"),
    ("baby", "Baby"),
    ("animal", "Animals"),
    ("car", "Cars"),
    ("graphic", "Graphics"),
]


def _find_sample(stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = SAMPLES_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _ver(p: Path) -> str:
    """Short token that changes whenever the sample file changes (cache-busting)."""
    st = p.stat()
    return f"{int(st.st_mtime)}-{st.st_size}"


def list_samples() -> list[dict]:
    out = []
    for stem, label in SAMPLE_CATEGORIES:
        p = _find_sample(stem)
        if p:
            v = _ver(p)
            out.append({"id": stem, "label": label,
                        "src": f"/samples/{p.name}?v={v}",
                        "nobg": f"/samples/{stem}/nobg.png?v={v}"})
    return out


def create_app(model: str = DEFAULT_MODEL):
    try:
        from flask import Flask, Response, abort, render_template_string, request, send_from_directory
    except ImportError as e:  # pragma: no cover
        raise SystemExit("The web UI needs Flask:  pip install 'bgeraser[web]'") from e

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB
    demo_cache: dict[str, bytes] = {}
    demo_lock = threading.Lock()

    @app.get("/")
    def index():
        return render_template_string(
            TEMPLATE, models=MODELS, default_model=model, samples=list_samples()
        )

    @app.get("/samples/<path:name>")
    def sample_file(name):
        return send_from_directory(SAMPLES_DIR, name)

    @app.get("/samples/<stem>/nobg.png")
    def sample_nobg(stem):
        """Background-removed version of a bundled sample, computed once and cached."""
        p = _find_sample(stem)
        if not p:
            abort(404)
        key = f"{stem}:{_ver(p)}:{model}"
        with demo_lock:
            if key not in demo_cache:
                demo_cache[key] = remove_background_bytes(p.read_bytes(), model=model)
        return Response(demo_cache[key], mimetype="image/png",
                        headers={"Cache-Control": "no-cache"})

    @app.post("/remove")
    def remove():
        f = request.files.get("image")
        if not f:
            return {"error": "no image uploaded"}, 400
        chosen = request.form.get("model") or model
        bg = request.form.get("bg") or None
        matting = request.form.get("matting") == "on"
        try:
            png = remove_background_bytes(f.read(), model=chosen, bg_color=bg, alpha_matting=matting)
        except ValueError as e:
            return {"error": str(e)}, 400
        except Exception as e:  # model download failure, bad image, etc.
            msg = f"{type(e).__name__}: {e}"
            print(f"[bgeraser] error: {msg}", flush=True)
            return {"error": msg}, 500
        stem = Path(f.filename or "image").stem
        return Response(
            png,
            mimetype="image/png",
            headers={"Content-Disposition": f'inline; filename="{stem}-nobg.png"'},
        )

    @app.get("/health")
    def health():
        return {"ok": True, "model": model}

    return app


def serve(host: str = "127.0.0.1", port: int = 5000, model: str = DEFAULT_MODEL) -> None:
    from .core import _get_session

    print(f"loading model '{model}' (downloads on first run, please wait)...", flush=True)
    try:
        _get_session(model)
    except Exception as e:
        print(f"could not load model: {type(e).__name__}: {e}\n"
              f"check your internet connection and run again.", flush=True)
        raise SystemExit(1)
    print("model ready", flush=True)

    app = create_app(model)
    print(f"bgeraser web UI -> http://{host}:{port}   (model: {model}, Ctrl+C to stop)", flush=True)
    app.run(host=host, port=port, debug=False, threaded=True)
