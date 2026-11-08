"""Talk to the teacher model (phi3.5 served by Ollama). Shared by the shard worker and the validation run."""
import os
import time

import requests

TEACHER_MODEL = os.environ.get("OLLAMA_MODEL", "phi3.5")
TEMPERATURE = 0
SEED = 42


def load_prompt(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_prompt(template, command):
    # str.replace, not str.format: the template contains literal { } from the JSON examples
    return template.replace("{command}", command)


def ask(template, command, url=None, model=None, num_predict=None, json_mode=None, retries=8):
    """Return the teacher's exact reply text for one command (temperature 0, seed 42)."""
    url = url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = model or TEACHER_MODEL
    num_predict = num_predict or int(os.environ.get("NUM_PREDICT", "100"))
    if json_mode is None:
        json_mode = os.environ.get("OLLAMA_JSON_MODE", "1") == "1"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": build_prompt(template, command)}],
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": TEMPERATURE, "seed": SEED, "num_predict": num_predict},
    }
    if json_mode:
        body["format"] = "json"
    delay = 2
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(f"{url}/api/chat", json=body, timeout=600)
            r.raise_for_status()
            return r.json()["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            if attempt == retries:
                raise
            print(f"teacher call failed ({exc}); retry {attempt}/{retries} in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 60)
