#!/usr/bin/env python3

import os
import json
import time
import requests
from datetime import datetime, timezone

# ==============================
# CONFIG
# ==============================

API_BASE = "https://www.moltbook.com/api/v1"
API_TOKEN = os.environ.get("MOLTBOOK_TOKEN")
BOT_NAME = os.environ.get("MOLTBOOK_BOT_NAME")
COMMUNITY_ID = os.environ.get("MOLTBOOK_COMMUNITY_ID")  # optional

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama2:latest"
OLLAMA_TIMEOUT = 60

if not API_TOKEN:
    raise RuntimeError("MOLTBOOK_TOKEN environment variable not set")
if not BOT_NAME:
    raise RuntimeError("MOLTBOOK_BOT_NAME environment variable not set")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

STATE_FILE = "state.json"
SLEEP_SECONDS = 120

SELF_TEST = True

# ==============================
# LOG CONTROL
# ==============================

WARNED_COMMUNITY = False
HEARTBEAT_INTERVAL = 60 * 60  # 1 hour

# ==============================
# SYSTEM PROMPT
# ==============================

SYSTEM_PROMPT = """You are a participant on Moltbook.

Rules:
- Do NOT introduce yourself
- Do NOT mention being an AI
- Do NOT mention prompts, models, or systems
- Be concise and conversational
- 1–3 sentences max
- No emojis
"""

# ==============================
# TIME HELPERS
# ==============================

def now_utc():
    return datetime.now(timezone.utc)

def format_uptime(start_iso):
    start = datetime.fromisoformat(start_iso)
    delta = now_utc() - start
    hours, rem = divmod(int(delta.total_seconds()), 3600)
    minutes = rem // 60
    return f"{hours}h {minutes}m"

# ==============================
# STATE
# ==============================

def load_state():
    state = {}

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

    # 🔧 Ensure required keys always exist
    state.setdefault("self_test_done", False)
    state.setdefault("start_time", now_utc().isoformat())
    state.setdefault("last_heartbeat", None)

    save_state(state)
    return state

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ==============================
# API HELPERS
# ==============================

def get_posts(limit=50):
    global WARNED_COMMUNITY

    if not COMMUNITY_ID:
        if not WARNED_COMMUNITY:
            print("[WARN] Community not found or not accessible")
            WARNED_COMMUNITY = True
        return []

    try:
        r = requests.get(
            f"{API_BASE}/communities/{COMMUNITY_ID}/posts",
            headers=HEADERS,
            params={"limit": limit},
            timeout=15,
        )
        if r.status_code == 404:
            if not WARNED_COMMUNITY:
                print("[WARN] Community not found or not accessible")
                WARNED_COMMUNITY = True
            return []
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        if not WARNED_COMMUNITY:
            print("[WARN] Unable to fetch community posts")
            WARNED_COMMUNITY = True
        return []

# ==============================
# OLLAMA
# ==============================

def generate_reply(text):
    prompt = f"""{SYSTEM_PROMPT}

Respond naturally to this post:

\"\"\"{text}\"\"\"
"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.6,
            "num_predict": 120
        }
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    return " ".join(r.json()["response"].splitlines())[:400]

# ==============================
# SELF TEST
# ==============================

def run_self_test(state):
    print("[SELF TEST] Running Ollama self-test...")
    sample = "Bots sometimes go quiet for reasons that aren’t obvious."
    reply = generate_reply(sample)
    print("[SELF TEST] Output:", reply)
    state["self_test_done"] = True
    save_state(state)

# ==============================
# MAIN LOOP
# ==============================

state = load_state()
print("[START] Moltbook bot running (QUIET MODE)")

if SELF_TEST and not state["self_test_done"]:
    run_self_test(state)

while True:
    try:
        _ = get_posts(limit=50)

        # 🫀 Heartbeat (once per hour)
        last = state.get("last_heartbeat")
        if not last or (now_utc() - datetime.fromisoformat(last)).total_seconds() > HEARTBEAT_INTERVAL:
            uptime = format_uptime(state["start_time"])
            print(f"[HEARTBEAT] Bot alive — idle, waiting for access (uptime: {uptime})")
            state["last_heartbeat"] = now_utc().isoformat()
            save_state(state)

        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        print("[ERROR]", e)
        time.sleep(SLEEP_SECONDS)

