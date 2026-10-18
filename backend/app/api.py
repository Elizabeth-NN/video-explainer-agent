import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


BACKEND_DIR = Path(__file__).resolve().parents[1]
JOBS_DIR = BACKEND_DIR / "generated" / "web_jobs"

app = FastAPI(title="Video Explainer Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

executor = ThreadPoolExecutor(max_workers=1)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


class CreateJobRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    use_gemini: bool = False
    voice: str = "en-US-JennyNeural"


def update_job(job_id: str, **changes) -> None:
    with jobs_lock:
        jobs[job_id].update(changes)


def run_generation(job_id: str, request: CreateJobRequest) -> None:
    output_dir = JOBS_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-u",
        "run_graph.py",
        request.topic,
        "--video",
        "--voice",
        request.voice,
        "--output-dir",
        str(output_dir),
    ]

    if request.use_gemini:
        command.append("--gemini")

    update_job(job_id, status="running")

    try:
        process = subprocess.Popen(
            command,
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        log_lines: list[str] = []

        assert process.stdout is not None
        for line in process.stdout:
            log_lines.append(line.rstrip())
            log_lines = log_lines[-100:]
            update_job(job_id, logs=log_lines.copy())

        return_code = process.wait()
        video_path = output_dir / "explainer.mp4"

        if return_code != 0:
            update_job(
                job_id,
                status="failed",
                error="Video generation failed. Inspect the job logs.",
                logs=log_lines,
            )
        elif not video_path.is_file():
            update_job(
                job_id,
                status="failed",
                error="The CLI finished without producing the expected MP4.",
                logs=log_lines,
            )
        else:
            update_job(
                job_id,
                status="completed",
                video_path=str(video_path),
                logs=log_lines,
            )

    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
        )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs", status_code=202)
def create_job(request: CreateJobRequest):
    job_id = str(uuid.uuid4())

    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "topic": request.topic.strip(),
            "status": "queued",
            "logs": [],
            "error": None,
            "video_path": None,
        }

    executor.submit(run_generation, job_id, request)

    return {
        "job_id": job_id,
        "topic": request.topic.strip(),
        "status": "queued",
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        result = job.copy()

    result.pop("video_path", None)
    return result


@app.get("/api/jobs/{job_id}/video")
def download_video(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        video_path = job.get("video_path")

    if not video_path or not Path(video_path).is_file():
        raise HTTPException(
            status_code=409,
            detail="The video is not ready for download.",
        )

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename="explainer.mp4",
    )
