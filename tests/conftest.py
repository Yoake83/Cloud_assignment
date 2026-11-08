import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for sub in ("worker", "service", "eval"):
    sys.path.insert(0, os.path.join(ROOT, sub))
os.environ.setdefault("SCHEMA_PATH", os.path.join(ROOT, "data", "schema.json"))
