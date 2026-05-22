import hashlib
import json
import os

STATE_FILE = "last_upload_state.json"


def _normalize_values(values):
    return json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":")
    )


def calculate_payload_hash(shifts_values, events_values):
    payload = {
        "shifts": shifts_values,
        "events": events_values,
    }
    normalized = _normalize_values(payload)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_last_hash(state_file=STATE_FILE):
    if not os.path.isfile(state_file):
        return None

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("payload_hash")
    except Exception:
        return None


def save_last_hash(payload_hash, state_file=STATE_FILE):
    data = {"payload_hash": payload_hash}
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)