"""Single-GPU durable job queue. No model imports in the HTTP process."""
from dataclasses import dataclass
from io import BytesIO
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4
import warnings

from PIL import Image, ImageOps
from face_regions import prepare_masks

ROOT = Path(__file__).resolve().parent
SCENES = {
    "A quiet morning in a sunlit garden",
    "A peaceful evening with a book",
    "A relaxed afternoon at a café",
}
LABEL = "AI-generated illustration—not a prediction of your appearance or health."
MAX_UPLOAD = 10 * 1024 * 1024
MAX_PIXELS = 4_000_000


class JobError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


@dataclass(frozen=True)
class WorkerSettings:
    root: Path
    token: str
    device: str = "cuda"
    ttl: int = 1800
    timeout: int = 300
    max_pending: int = 4
    max_per_owner: int = 6

    def __post_init__(self):
        if len(self.token) < 32:
            raise ValueError("MODEL_SERVICE_TOKEN must contain at least 32 characters")
        if self.device not in {"cuda", "mps"}:
            raise ValueError("MODEL_DEVICE must be cuda or mps")
        if min(self.ttl, self.timeout, self.max_pending, self.max_per_owner) <= 0:
            raise ValueError("Worker limits must be positive")

    @classmethod
    def from_env(cls):
        return cls(Path(os.getenv("MODEL_JOB_DIR", str(ROOT / ".local/cloud-jobs"))),
                   os.environ.get("MODEL_SERVICE_TOKEN", ""), os.getenv("MODEL_DEVICE", "cuda"),
                   int(os.getenv("MODEL_JOB_TTL_SECONDS", "1800")),
                   int(os.getenv("MODEL_TIMEOUT_SECONDS", "300")))


def validate_input(raw, options):
    if len(raw) > MAX_UPLOAD:
        raise JobError(413, "Choose an image under 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(raw))
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > MAX_PIXELS:
                raise ValueError()
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.load()
            image.info.clear()  # Pillow can otherwise carry EXIF into a re-encoded PNG.
        if not isinstance(options, dict) or set(options) - {"mode", "scenario", "face_box", "edit_box", "strength", "finish", "size", "steps", "seed"}:
            raise ValueError()
        mode = options.get("mode", "scene")
        fields = {"mode": mode, "size": options.get("size", 512),
                  "steps": options.get("steps", 30 if mode == "face-edit" else 20),
                  "seed": options.get("seed", 42)}
        if type(fields["size"]) is not int or fields["size"] not in {512, 768}:
            raise ValueError()
        if type(fields["steps"]) is not int or not 10 <= fields["steps"] <= 50:
            raise ValueError()
        if type(fields["seed"]) is not int or not 0 <= fields["seed"] < 2**32:
            raise ValueError()
        if mode == "face-edit":
            for key in ("face_box", "edit_box"):
                box = options.get(key)
                if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box):
                    raise ValueError()
                fields[key] = box
            if fields["face_box"][2] - fields["face_box"][0] < 64:
                raise ValueError()
            prepare_masks(image, fields["face_box"], edit_box=fields["edit_box"])
            fields.update(strength=options.get("strength", 0.25), finish=options.get("finish", "original"))
            if fields["strength"] not in (0.15, 0.25) or fields["finish"] not in ("original", "soft-light"):
                raise ValueError()
            if "scenario" in options:
                raise ValueError()
        elif mode == "scene":
            fields["scenario"] = options.get("scenario")
            if not isinstance(fields["scenario"], str) or fields["scenario"] not in SCENES:
                raise ValueError()
            if set(options) & {"face_box", "edit_box", "strength", "finish"}:
                raise ValueError()
        else:
            raise ValueError()
        return image, fields
    except JobError:
        raise
    except Exception as exc:
        raise JobError(422, "Use a valid JPG, PNG, or WebP up to four megapixels and supported illustration settings.") from exc


def run_model(folder, fields, cancel, progress, settings):
    script = "run_face_edit.py" if fields["mode"] == "face-edit" else "run_local.py"
    progress_path = folder / "progress.json"
    command = [sys.executable, str(ROOT / script), "--device", settings.device,
               "--reference", str(folder / "input.png"), "--output-dir", str(folder / "result"),
               "--progress-file", str(progress_path), "--size", str(fields["size"]),
               "--steps", str(fields["steps"]), "--seed", str(fields["seed"])]
    if fields["mode"] == "face-edit":
        command += ["--face-box", *map(str, fields["face_box"]), "--edit-box", *map(str, fields["edit_box"]),
                    "--strength", str(fields["strength"]), "--finish", fields["finish"]]
    else:
        command += ["--prompt", "Photographic portrait of the reference person. Natural skin texture, "
                    "realistic facial proportions, no beauty filter. Artistic setting: " + fields["scenario"]]
    with (folder / "worker.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + settings.timeout
            while process.poll() is None:
                if cancel.wait(0.1):
                    raise RuntimeError("cancelled")
                if time.monotonic() >= deadline:
                    raise TimeoutError("generation timed out")
                try:
                    steps = json.loads(progress_path.read_text())
                    if 0 < steps["totalSteps"] and 0 <= steps["completedSteps"] <= steps["totalSteps"]:
                        progress(steps["completedSteps"], steps["totalSteps"])
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            if process.returncode:
                raise RuntimeError("model process failed")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    report = json.loads((folder / "result/metrics.json").read_text())
    if report.get("status") != "success":
        raise RuntimeError("model report failed")
    if fields["mode"] == "face-edit" and report.get("changed_pixels_outside_mask") != 0:
        raise RuntimeError("region preservation failed")
    return folder / "result/illustration.png"


class JobQueue:
    def __init__(self, settings, runner=run_model):
        self.settings, self.runner = settings, runner
        self.root = settings.root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.active = {}  # job id -> (cancellation, completion)
        self.thread = None
        self.file_lock = None
        self.db = None

    def start(self):
        self.file_lock = (self.root / "worker.lock").open("a")
        try:
            fcntl.flock(self.file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.file_lock.close()
            raise RuntimeError("Only one worker process may use this job directory")
        self.db = sqlite3.connect(self.root / "jobs.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
            fingerprint TEXT NOT NULL, fields TEXT NOT NULL, status TEXT NOT NULL,
            created REAL NOT NULL, expires REAL NOT NULL, progress REAL,
            completed_steps INTEGER, total_steps INTEGER, error TEXT,
            UNIQUE(owner, request_key))""")
        # Separate from expiring image jobs: never infer usage from browser polling.
        self.db.execute("""CREATE TABLE IF NOT EXISTS usage_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE, owner TEXT NOT NULL,
            occurred_at REAL NOT NULL, quantity INTEGER NOT NULL CHECK(quantity=1),
            runtime_ms INTEGER NOT NULL CHECK(runtime_ms>=0),
            model TEXT NOT NULL, region TEXT NOT NULL)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS usage_owner_time ON usage_events(owner, occurred_at)")
        self.db.commit()
        # Never silently rerun interrupted generation (it could produce a different result).
        with self.db:
            self.db.execute("UPDATE jobs SET status='failed', error='The worker restarted. Please submit a new job.' WHERE status IN ('queued','running')")
        for folder in self.root.iterdir():
            if folder.is_dir() and not folder.is_symlink() and self._valid_id(folder.name):
                row = self.db.execute("SELECT status FROM jobs WHERE id=?", (folder.name,)).fetchone()
                if row is None or row["status"] != "completed":
                    shutil.rmtree(folder)
                else:
                    self._clean_intermediates(folder)
        self.thread = threading.Thread(target=self._loop, daemon=True, name="rest-gpu-worker")
        self.thread.start()

    @staticmethod
    def _valid_id(value):
        try:
            return str(UUID(value)) == value
        except (ValueError, TypeError):
            return False

    def _owned(self, owner, key):
        row = self.db.execute("SELECT * FROM jobs WHERE id=? AND owner=? AND expires>?", (key, owner, time.time())).fetchone()
        if row is None:
            raise JobError(404, "Job not found or expired.")
        return row

    def _public(self, row):
        result = {"id": row["id"], "status": row["status"], "mode": json.loads(row["fields"])["mode"],
                  "createdAt": row["created"], "expiresAt": row["expires"], "disclaimer": LABEL}
        if row["progress"] is not None:
            result.update(progress=row["progress"], progressStage="denoising",
                          completedSteps=row["completed_steps"], totalSteps=row["total_steps"])
        if row["status"] == "failed":
            result["error"] = row["error"]
        return result

    def create(self, owner, request_key, raw, options):
        image, fields = validate_input(raw, options)
        fingerprint = hashlib.sha256(raw + json.dumps(fields, sort_keys=True).encode()).hexdigest()
        self.cleanup()
        with self.lock:
            prior = self.db.execute("SELECT * FROM jobs WHERE owner=? AND request_key=?", (owner, request_key)).fetchone()
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise JobError(409, "This request key was already used for different input.")
                return self._public(prior)
            pending = self.db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            count = self.db.execute("SELECT count(*) FROM jobs WHERE owner=?", (owner,)).fetchone()[0]
            if pending >= self.settings.max_pending or count >= self.settings.max_per_owner:
                raise JobError(429, "The illustration queue is full. Try again later or delete an older job.")
            key, now = str(uuid4()), time.time()
            folder = self.root / key
            folder.mkdir(mode=0o700)
            try:
                image.save(folder / "input.png")  # decode/re-encode strips original metadata
                with self.db:
                    self.db.execute("INSERT INTO jobs(id,owner,request_key,fingerprint,fields,status,created,expires) VALUES(?,?,?,?,?,'queued',?,?)",
                                    (key, owner, request_key, fingerprint, json.dumps(fields), now, now + self.settings.ttl))
            except Exception:
                shutil.rmtree(folder, ignore_errors=True)
                raise
            self.wake.set()
            return self._public(self._owned(owner, key))

    def status(self, owner, key):
        with self.lock:
            return self._public(self._owned(owner, key))

    def list(self, owner):
        with self.lock:
            return [self._public(r) for r in self.db.execute("SELECT * FROM jobs WHERE owner=? AND expires>? ORDER BY created", (owner, time.time()))]

    def usage(self, owner, after=0, limit=100):
        with self.lock:
            rows = list(self.db.execute(
                "SELECT * FROM usage_events WHERE owner=? AND sequence>? ORDER BY sequence LIMIT ?",
                (owner, after, limit + 1)))
            items = [{"sequence": r["sequence"], "eventId": r["event_id"],
                      "customerId": r["owner"], "occurredAt": r["occurred_at"],
                      "metric": "illustration.completed", "quantity": r["quantity"],
                      "runtimeMs": r["runtime_ms"], "model": r["model"], "region": r["region"],
                      "schemaVersion": 1} for r in rows[:limit]]
            return {"items": items, "nextCursor": items[-1]["sequence"] if len(rows) > limit else None}

    def purge_usage(self, owner):
        with self.lock, self.db:
            return self.db.execute("DELETE FROM usage_events WHERE owner=?", (owner,)).rowcount

    def image(self, owner, key):
        with self.lock:
            row = self._owned(owner, key)
            if row["status"] != "completed":
                raise JobError(409, "The image is not ready.")
            path = self.root / key / "illustration.png"
            if not path.is_file():
                raise JobError(410, "The image is no longer available.")
            return path.read_bytes()

    def delete(self, owner, key, expired=False):
        with self.lock:
            if expired:
                row = self.db.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (key, owner)).fetchone()
                if row is None:
                    return
            else:
                self._owned(owner, key)
            active = self.active.get(key)
            if active:
                active[0].set()
            else:
                # Claim/delete is atomic with the worker's claim, so it cannot start afterward.
                self._remove(key)
                return
        if not active[1].wait(10):
            raise JobError(503, "Cancellation is still finishing. Please retry deletion.")
        with self.lock:
            self._remove(key)

    def purge(self, owner):
        with self.lock:
            keys = [r[0] for r in self.db.execute("SELECT id FROM jobs WHERE owner=?", (owner,))]
        for key in keys:
            self.delete(owner, key, expired=True)
        return len(keys)

    def _remove(self, key):
        if (self.root / key).exists():
            shutil.rmtree(self.root / key)
        with self.db:
            self.db.execute("DELETE FROM jobs WHERE id=?", (key,))

    def cleanup(self):
        with self.lock:
            rows = list(self.db.execute("SELECT owner,id FROM jobs WHERE expires<=?", (time.time(),)))
        for row in rows:
            self.delete(row["owner"], row["id"], expired=True)

    @staticmethod
    def _clean_intermediates(folder):
        for path in folder.iterdir():
            if path.name == "illustration.png":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)

    def _loop(self):
        while not self.stop.is_set():
            try:
                self.cleanup()
            except (OSError, JobError):
                logging.getLogger(__name__).error("Temporary job cleanup failed; will retry")
                self.stop.wait(1)
                continue
            with self.lock:
                row = self.db.execute("SELECT * FROM jobs WHERE status='queued' AND expires>? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
                if row:
                    key = row["id"]
                    cancel, done = threading.Event(), threading.Event()
                    self.active[key] = cancel, done
                    with self.db:
                        self.db.execute("UPDATE jobs SET status='running' WHERE id=?", (key,))
            if row is None:
                self.wake.wait(1)
                self.wake.clear()
                continue
            folder = self.root / key
            def progress(completed, total):
                with self.lock, self.db:
                    self.db.execute("UPDATE jobs SET progress=?,completed_steps=?,total_steps=? WHERE id=?",
                                    (100 * completed / total, completed, total, key))
            expiry = threading.Timer(max(0, row["expires"] - time.time()), cancel.set)
            expiry.start()
            started = time.monotonic()
            try:
                output = self.runner(folder, json.loads(row["fields"]), cancel, progress, self.settings)
                if cancel.is_set():
                    raise RuntimeError("cancelled")
                with Image.open(output) as image:
                    image.verify()
                shutil.copyfile(output, folder / "illustration.png")
                self._clean_intermediates(folder)
                with self.lock, self.db:
                    if cancel.is_set() or time.time() >= row["expires"]:
                        raise RuntimeError("cancelled or expired before completion")
                    self.db.execute("UPDATE jobs SET status='completed' WHERE id=?", (key,))
                    self.db.execute("""INSERT INTO usage_events
                        (event_id,owner,occurred_at,quantity,runtime_ms,model,region)
                        VALUES(?,?,?,1,?,?,?)""",
                        (key, row["owner"], time.time(), max(0, round((time.monotonic()-started)*1000)),
                         "sdxl-ip-adapter-plus-face-v1", os.getenv("AWS_REGION", "local")))
            except Exception:
                with self.lock, self.db:
                    self.db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",
                                    ("Generation did not finish. Please try again.", key))
            finally:
                expiry.cancel()
                try:
                    self._clean_intermediates(folder)
                except OSError:
                    logging.getLogger(__name__).error("Job cleanup failed; deletion must be retried")
                finally:
                    with self.lock:
                        self.active.pop(key, None)
                        done.set()

    def close(self):
        self.stop.set()
        self.wake.set()
        with self.lock:
            for cancel, _ in self.active.values():
                cancel.set()
        if self.thread:
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                raise RuntimeError("Worker did not stop cleanly")
        if self.db:
            self.db.close()
        if self.file_lock:
            self.file_lock.close()
