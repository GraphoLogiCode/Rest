"""Loopback-only development API. Start with: .venv/bin/python local_api.py

No public deployment: the main Rest authentication API remains separate.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from io import BytesIO
import json
import ipaddress
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
import warnings
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from face_regions import prepare_masks

ROOT = Path(__file__).resolve().parent
TTL = 30 * 60
COOKIE = "rest_illustration_session"
MAX_BODY = 11 * 1024 * 1024
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


def configured_origins(extra):
    """Opt in to exact preview IP origins, without wildcards or DNS names."""
    origins = set(ALLOWED_ORIGINS)
    for origin in filter(None, (item.strip() for item in extra.split(','))):
        value = urlsplit(origin)
        host = value.hostname
        local = host == 'localhost'
        if not local:
            try:
                address = ipaddress.ip_address(host or '')
                local = not (address.is_unspecified or address.is_multicast or address.is_reserved)
            except ValueError:
                local = False
        if (not local or value.scheme not in {'http', 'https'} or not value.port
                or value.username or value.password or value.path or value.query or value.fragment):
            raise ValueError('REST_PREVIEW_ORIGINS must contain exact localhost or unicast IP origins with a port')
        origins.add(origin)
    return origins


def run_model(folder, fields, register):
    command = [sys.executable, str(ROOT / "run_face_edit.py"), "--reference", str(folder / "input.png"),
               "--face-box", *map(str, fields["face_box"]), "--edit-box", *map(str, fields["edit_box"]),
               "--strength", str(fields["strength"]), "--finish", fields["finish"],
               "--output-dir", str(folder / "result")]
    with (folder / "worker.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        register(process)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError("The local GPU job timed out. Try a smaller selection.")
        if code:
            raise RuntimeError("The local model could not finish. Check the local service terminal.")


def create_app(work_root=None, runner=run_model):
    allowed_origins = configured_origins(os.getenv('REST_PREVIEW_ORIGINS', ''))
    work_root = Path(work_root or ROOT / ".local/api-jobs")
    work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    jobs, sessions = {}, {}
    lock = threading.RLock()
    executor = ThreadPoolExecutor(max_workers=1)
    stop = threading.Event()

    def dispose(job):
        job["cancelled"] = True
        if job.get("process") and job["process"].poll() is None:
            job["process"].terminate()
        if job["status"] != "running":
            shutil.rmtree(job["folder"], ignore_errors=True)

    def cleanup():
        with lock:
            now = time.time()
            for key, job in list(jobs.items()):
                if job["expires"] < now:
                    dispose(job)
                    del jobs[key]
            for key, expires in list(sessions.items()):
                if expires < now:
                    del sessions[key]

    def janitor():
        while not stop.wait(30):
            cleanup()

    @asynccontextmanager
    async def lifespan(app):
        # This folder contains only this service's temporary UUID jobs.
        for path in work_root.iterdir():
            if path.is_dir() and not path.is_symlink() and len(path.name) == 32 and all(c in "0123456789abcdef" for c in path.name):
                shutil.rmtree(path)
        thread = threading.Thread(target=janitor, daemon=True)
        thread.start()
        yield
        stop.set()
        with lock:
            for job in jobs.values():
                dispose(job)
        executor.shutdown(wait=True, cancel_futures=True)
        for job in jobs.values():
            shutil.rmtree(job["folder"], ignore_errors=True)

    app = FastAPI(title="Rest local face preview", lifespan=lifespan)

    @app.middleware("http")
    async def local_only(request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return Response(status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in allowed_origins:
            return Response(status_code=403)
        if request.method == "POST":
            try:
                size = int(request.headers.get("content-length", "-1"))
            except ValueError:
                return Response(status_code=400)
            if size < 0 or size > MAX_BODY:
                return Response(status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def owner(request):
        token = request.cookies.get(COOKIE)
        with lock:
            if not token or sessions.get(token, 0) < time.time():
                raise HTTPException(401, "Start a new local preview session.")
        return token

    def owned(request, key):
        token = owner(request)
        with lock:
            job = jobs.get(key)
            if not job or job["owner"] != token or job["expires"] < time.time():
                raise HTTPException(404, "Preview not found or expired.")
            return job

    def public(job):
        value = {"id": job["id"], "status": job["status"],
                 "productNote": job["product"], "expiresAt": job["expires"],
                 "disclaimer": "AI illustration, not a predicted product result."}
        if job["status"] == "completed":
            value["imageUrl"] = f"jobs/{job['id']}/image"
        if job.get("error"):
            value["error"] = job["error"]
        return value

    def worker(job, fields):
        with lock:
            if job["cancelled"]:
                return
            job["status"] = "running"
        def register(process):
            with lock:
                job["process"] = process
                if job["cancelled"]:
                    process.terminate()
        try:
            runner(job["folder"], fields, register)
            report = json.loads((job["folder"] / "result/metrics.json").read_text())
            if report.get("status") != "success" or report.get("changed_pixels_outside_mask") != 0:
                raise RuntimeError("The preview did not pass its region-preservation check.")
            if not (job["folder"] / "result/illustration.png").is_file():
                raise RuntimeError("No preview image was produced.")
            with lock:
                job["status"] = "completed"
        except Exception as exc:
            with lock:
                job["status"] = "failed"
                job["error"] = str(exc) if isinstance(exc, RuntimeError) else "The preview failed. Try again."
        finally:
            # Remove uploaded/reference images, masks, logs, and intermediate copies.
            for path in job["folder"].rglob("*"):
                if path.is_file() and path.name != "illustration.png":
                    path.unlink(missing_ok=True)
            if job["cancelled"]:
                shutil.rmtree(job["folder"], ignore_errors=True)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "local-development", "retentionMinutes": 30}

    @app.post("/session")
    def session(request: Request, response: Response):
        token = request.cookies.get(COOKIE)
        with lock:
            if not token or sessions.get(token, 0) < time.time():
                token = secrets.token_urlsafe(32)
            sessions[token] = time.time() + TTL
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=TTL, path="/")
        return {"status": "ready"}

    @app.post("/jobs", status_code=202)
    async def create(request: Request):
        token = owner(request)
        form = await request.form(max_files=1, max_fields=8)
        try:
            if form.get("consent") != "true":
                raise HTTPException(400, "Consent is required for this preview.")
            upload = form.get("reference")
            if not hasattr(upload, "read"):
                raise ValueError("Choose a photo.")
            raw = await upload.read(10 * 1024 * 1024 + 1)
            if len(raw) > 10 * 1024 * 1024:
                raise ValueError("Choose an image under 10 MB.")
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = Image.open(BytesIO(raw))
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 4_000_000:
                    raise ValueError("Use JPG, PNG or WebP, up to four megapixels.")
                image = ImageOps.exif_transpose(image).convert("RGB")
            face = json.loads(str(form.get("face_box", "null")))
            edit = json.loads(str(form.get("edit_box", "null")))
            for box in (face, edit):
                if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
                    raise ValueError("Select a face and an edit region.")
            if face[2] - face[0] < 64:
                raise ValueError("Select a larger face region (at least 64 pixels).")
            prepare_masks(image, face, edit_box=edit)
            finish = str(form.get("finish", "original"))
            strength = float(str(form.get("strength", "0.25")))
            if finish not in {"original", "soft-light"} or strength not in {0.15, 0.25}:
                raise ValueError("Choose a supported preview setting.")
            product = str(form.get("product", "")).strip()[:120]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else "This image could not be opened.") from exc
        finally:
            await form.close()
        with lock:
            if sum(j["status"] in {"queued", "running"} for j in jobs.values()) >= 4:
                raise HTTPException(429, "The local preview queue is full. Try again shortly.")
            if sum(j["owner"] == token for j in jobs.values()) >= 6:
                raise HTTPException(429, "Delete an older preview before creating another.")
            key = secrets.token_hex(16)
            folder = work_root / key
            folder.mkdir(mode=0o700)
            image.save(folder / "input.png")
            job = {"id": key, "owner": token, "folder": folder, "status": "queued",
                   "expires": time.time() + TTL, "product": product, "cancelled": False}
            jobs[key] = job
            executor.submit(worker, job, {"face_box": face, "edit_box": edit, "finish": finish, "strength": strength})
            return public(job)

    @app.get("/jobs/{key}")
    def status(key: str, request: Request):
        with lock:
            return public(owned(request, key))

    @app.get("/jobs/{key}/image")
    def image(key: str, request: Request):
        job = owned(request, key)
        if job["status"] != "completed":
            raise HTTPException(409, "Preview is not ready.")
        return FileResponse(job["folder"] / "result/illustration.png", media_type="image/png")

    @app.delete("/jobs/{key}", status_code=204)
    def delete(key: str, request: Request):
        with lock:
            job = owned(request, key)
            dispose(job)
            del jobs[key]
        return Response(status_code=204)

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8766, access_log=False)
