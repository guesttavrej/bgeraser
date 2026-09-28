"""Tiny local web UI: `bgeraser serve` then open http://127.0.0.1:5000."""

from __future__ import annotations

from pathlib import Path

from .core import DEFAULT_MODEL, MODELS, remove_background_bytes

TEMPLATE = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")


def create_app(model: str = DEFAULT_MODEL):
    try:
        from flask import Flask, Response, render_template_string, request
    except ImportError as e:  # pragma: no cover
        raise SystemExit("The web UI needs Flask:  pip install 'bgeraser[web]'") from e

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB

    @app.get("/")
    def index():
        return render_template_string(TEMPLATE, models=MODELS, default_model=model)

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
    app = create_app(model)
    print(f"bgeraser web UI -> http://{host}:{port}   (model: {model}, Ctrl+C to stop)")
    app.run(host=host, port=port, debug=False)
