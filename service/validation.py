"""Check a model output against schema.json. Returns the object (keys in schema order) or None."""
import json
import os

from jsonschema import Draft202012Validator

SCHEMA_PATH = os.environ.get("SCHEMA_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.json"))
if not os.path.exists(SCHEMA_PATH):  # running from a repository checkout
    SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "schema.json")

with open(SCHEMA_PATH, encoding="utf-8") as _f:
    _schema = json.load(_f)
KEYS = _schema["keys"]
_validator = Draft202012Validator(_schema["json_schema"])


def validate_output(raw):
    try:
        obj = json.loads(str(raw).strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or not _validator.is_valid(obj):
        return None
    return {k: obj[k] for k in KEYS}
