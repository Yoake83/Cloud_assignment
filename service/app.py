"""Command-parser service.  POST /parse, GET /healthz, GET /readyz.

Configuration (environment): MODEL_URI, MODEL_VERSION, S3_ENDPOINT, MAX_NEW_TOKENS, FAULT_INJECT (0/1).
S3 credentials (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) come from a Kubernetes Secret.
"""
import os
import tempfile
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from validation import validate_output

MODEL_DIR = os.path.join(tempfile.gettempdir(), "model")


class State:
    model = None
    ready = False
    error = None
    load_seconds = None


state = State()


def load_model():
    """Download from object storage and load. Replaced by a stub in the unit tests."""
    from inference import Student
    from storage import download_model

    n = download_model(os.environ["MODEL_URI"], MODEL_DIR, os.environ["S3_ENDPOINT"])
    print(f"downloaded {n} files from {os.environ['MODEL_URI']}", flush=True)
    return Student(MODEL_DIR)


def _load_in_background():
    t0 = time.time()
    try:
        state.model = load_model()
        state.load_seconds = round(time.time() - t0, 1)
        state.ready = True
        print(f"model ready after {state.load_seconds}s", flush=True)
    except Exception as exc:  # keep the process alive so /healthz stays 200 and the failure is visible
        state.error = repr(exc)
        print("MODEL LOAD FAILED:", state.error, flush=True)


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_load_in_background, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


class ParseRequest(BaseModel):
    text: str


def _headers():
    return {
        "X-Model-Version": os.environ.get("MODEL_VERSION", "unknown"),
        "X-Served-By": os.environ.get("POD_NAME") or os.environ.get("HOSTNAME", "unknown"),
    }


@app.get("/healthz")
async def healthz():
    return {"status": "alive"}


@app.get("/readyz")
async def readyz():
    if state.ready:
        return {"status": "ready"}
    return JSONResponse({"status": "loading", "error": state.error}, status_code=503)


@app.post("/parse")
def parse(req: ParseRequest):
    headers = _headers()
    if not state.ready:
        return JSONResponse({"error": "model_not_ready"}, status_code=503, headers=headers)
    raw = state.model.generate(req.text, int(os.environ.get("MAX_NEW_TOKENS", "80")))
    if os.environ.get("FAULT_INJECT", "0") == "1":
        raw = "not json"
    obj = validate_output(raw)
    if obj is None:
        return JSONResponse({"error": "invalid_model_output"}, status_code=500, headers=headers)
    return JSONResponse(obj, status_code=200, headers=headers)
