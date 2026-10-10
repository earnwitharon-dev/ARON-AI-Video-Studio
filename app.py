
from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
from PIL import Image, ImageOps
from huggingface_hub import HfApi
from gradio_client import Client, handle_file
import threading, uuid, shutil, subprocess, requests

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024

DEFAULT_SPACE = "r3gm/wan2-2-fp8da-aoti-preview"
DEFAULT_API = "/generate_video"
MIN_SAFE_QUOTA_SECONDS = 120
DEFAULT_NEGATIVE = (
    "blurry, low quality, distorted, deformed, watermark, text, subtitles, "
    "bad anatomy, extra fingers, bad hands, bad face, duplicate people, "
    "shaky camera, static frame, jpeg artifacts"
)

jobs = {}
jobs_lock = threading.Lock()

def set_job(job_id, **kwargs):
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(kwargs)

def get_job(job_id):
    with jobs_lock:
        return dict(jobs.get(job_id, {}))

def ffmpeg_exists():
    return shutil.which("ffmpeg") is not None

def preprocess_9x16(src, dst):
    with Image.open(src) as im:
        im = im.convert("RGB")
        fitted = ImageOps.fit(im, (480, 832), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(dst, quality=95)

def quota_info(token):
    if not token:
        return {
            "mode": "anonymous",
            "safe": True,
            "remaining": None,
            "message": "Anonymous ZeroGPU mode: no billing path. Shared free quota/queue applies."
        }
    try:
        api = HfApi(token=token)
        q = api.get_zero_gpu_quota()
        remaining = float(q.remaining or 0)
        base = float(q.base or 0)
        reset = q.resets_at.isoformat() if q.resets_at else None
        over = float(q.overquota_used or 0)
        safe = remaining >= MIN_SAFE_QUOTA_SECONDS and over <= 0
        return {
            "mode": "authenticated",
            "safe": safe,
            "remaining": round(remaining, 1),
            "base": round(base, 1),
            "resets_at": reset,
            "overquota_used": round(over, 1),
            "message": (
                f"Free ZeroGPU remaining: {remaining:.0f}s."
                if safe else
                f"Generation locked: only {remaining:.0f}s included ZeroGPU quota remains."
            )
        }
    except Exception as e:
        return {
            "mode": "authenticated",
            "safe": False,
            "remaining": None,
            "message": "Could not verify included ZeroGPU quota. Hard ₱0 lock refuses generation. "
                       "Use Anonymous Free Mode or a token that can read ZeroGPU quota.",
            "detail": str(e)
        }

def resolve_video(result):
    item = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(item, dict):
        candidate = item.get("path") or item.get("url") or item.get("video")
    else:
        candidate = str(item)
    if not candidate:
        raise RuntimeError("The ZeroGPU Space returned no video file.")
    if candidate.startswith("http://") or candidate.startswith("https://"):
        tmp = OUTPUTS / ("remote_" + uuid.uuid4().hex + ".mp4")
        r = requests.get(candidate, timeout=180)
        r.raise_for_status()
        tmp.write_bytes(r.content)
        return tmp
    p = Path(candidate)
    if not p.exists():
        raise RuntimeError(f"Generated video path was not found: {candidate}")
    return p

def normalize_vertical(src, dst):
    if not ffmpeg_exists():
        shutil.copy2(src, dst)
        return False
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-an", "-movflags", "+faststart", str(dst)
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        shutil.copy2(src, dst)
        return False
    return True

def run_generation(job_id, ref_path, prompt, duration, token, space_id):
    try:
        set_job(job_id, status="checking", progress=8, message="Checking the ₱0 safety lock…")
        q = quota_info(token)
        set_job(job_id, quota=q)
        if not q.get("safe"):
            raise RuntimeError(q.get("message", "Free quota safety check failed."))

        prepared = UPLOADS / f"{job_id}_9x16.jpg"
        preprocess_9x16(Path(ref_path), prepared)

        set_job(job_id, status="queueing", progress=20, message="Connecting to free ZeroGPU queue…")
        client = Client(space_id, token=token or None, verbose=False)

        set_job(job_id, status="generating", progress=35,
                message="ZeroGPU is generating your scene. Queue time can vary.")

        result = client.predict(
            handle_file(str(prepared)),
            None,
            prompt,
            4,
            DEFAULT_NEGATIVE,
            float(duration),
            1.0,
            1.0,
            42,
            True,
            api_name=DEFAULT_API,
        )

        set_job(job_id, status="processing", progress=82,
                message="Generation finished. Preparing exact 9:16 MP4…")

        generated = resolve_video(result)
        final_name = f"ARON_FREE_{job_id}.mp4"
        final_path = OUTPUTS / final_name
        exact = normalize_vertical(generated, final_path)

        set_job(job_id, status="done", progress=100,
                message="Ready — generated using free ZeroGPU only.",
                output=f"/outputs/{final_name}", filename=final_name, exact_9x16=exact)
    except Exception as e:
        set_job(job_id, status="error", progress=100, message=str(e), error=str(e))

@app.get("/")
def index():
    return render_template("index.html", default_space=DEFAULT_SPACE)

@app.post("/api/quota")
def api_quota():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    return jsonify(quota_info(token))

@app.post("/api/generate")
def api_generate():
    f = request.files.get("reference")
    prompt = (request.form.get("prompt") or "").strip()
    token = (request.form.get("token") or "").strip()
    mode = request.form.get("mode", "anonymous")
    space_id = (request.form.get("space_id") or DEFAULT_SPACE).strip()

    if not f or not f.filename:
        return jsonify(ok=False, error="Upload a reference image first."), 400
    if not prompt:
        return jsonify(ok=False, error="Enter a motion prompt first."), 400
    if mode == "anonymous":
        token = ""

    try:
        duration = float(request.form.get("duration") or 3.0)
    except Exception:
        duration = 3.0
    duration = max(1.0, min(4.0, duration))

    q = quota_info(token)
    if not q.get("safe"):
        return jsonify(ok=False, error=q.get("message"), quota=q), 400

    job_id = uuid.uuid4().hex[:12]
    suffix = Path(f.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    src = UPLOADS / f"{job_id}_source{suffix}"
    f.save(src)

    set_job(job_id, status="queued", progress=3, message="Job created.", quota=q)
    threading.Thread(
        target=run_generation,
        args=(job_id, src, prompt, duration, token, space_id),
        daemon=True
    ).start()
    return jsonify(ok=True, job_id=job_id, quota=q)

@app.get("/api/status/<job_id>")
def api_status(job_id):
    j = get_job(job_id)
    if not j:
        return jsonify(ok=False, error="Job not found."), 404
    return jsonify(ok=True, **j)

@app.get("/outputs/<path:name>")
def outputs(name):
    return send_from_directory(OUTPUTS, name)

@app.get("/api/health")
def health():
    return jsonify(
        ok=True,
        provider="Hugging Face ZeroGPU Space only",
        paid_fallback=False,
        hard_spending_lock_php=0,
        ffmpeg=ffmpeg_exists(),
        default_space=DEFAULT_SPACE
    )

if __name__ == "__main__":
    print("\nARON AI Video Studio V1 FREE")
    print("Open: http://127.0.0.1:5188")
    print("Paid fallback: DISABLED | Hard spending lock: PHP 0\n")
    app.run(host="127.0.0.1", port=5188, debug=False)
