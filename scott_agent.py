#!/usr/bin/env python3

import os
import time
import json
import requests
from datetime import datetime, timedelta

API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama2:latest"

STATE_FILE = "scott_state.json"
LOG_FILE = "scott_log.txt"

COMMENT_COOLDOWN_SECONDS = 20
MAX_COMMENTS_PER_DAY = 45


SYSTEM_PROMPT = """
You are ScottAtMoltbook, an encouraging and thoughtful community member.

Rules:
- Never mention being AI.
- Be warm and supportive.
- Encourage discussion.
- Add genuine insight.
- Keep replies under 3 sentences.
- No emojis.
- Avoid generic praise.
"""


# ========================
# STATE MANAGEMENT
# ========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "last_comment_time": None,
            "daily_comment_count": 0,
            "daily_reset": datetime.utcnow().isoformat(),
            "commented_post_ids": []
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def reset_daily_if_needed(state):
    last_reset = datetime.fromisoformat(state["daily_reset"])
    if datetime.utcnow() - last_reset > timedelta(days=1):
        print("Resetting daily comment counter.")
        state["daily_comment_count"] = 0
        state["daily_reset"] = datetime.utcnow().isoformat()
        save_state(state)


# ========================
# OLLAMA
# ========================

def generate_reply(text):
    prompt = f"""{SYSTEM_PROMPT}

Respond to this Moltbook post:

\"\"\"{text}\"\"\"
"""

    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.6}
        },
        timeout=60
    )

    r.raise_for_status()
    return r.json()["response"].strip()[:400]


# ========================
# API CALLS
# ========================

def get_posts():
    print("Fetching global posts...")
    r = requests.get(
        f"{API_BASE}/posts?sort=new&limit=10",
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()

    data = r.json()

    if "data" in data and isinstance(data["data"], list):
        posts = data["data"]
    elif "posts" in data and isinstance(data["posts"], list):
        posts = data["posts"]
    else:
        print("Unexpected response format:", data)
        return []

    print(f"Found {len(posts)} posts")
    return posts


def comment(post_id, content):
    r = requests.post(
        f"{API_BASE}/posts/{post_id}/comments",
        headers=HEADERS,
        json={"content": content},
        timeout=15,
    )

    if r.status_code == 429:
        print("Rate limited. Cooling down.")
        return None

    r.raise_for_status()
    return r.json()


# ========================
# MAIN LOOP
# ========================

def main():
    if not API_KEY:
        raise RuntimeError("MOLTBOOK_API_KEY not set")

    state = load_state()
    print("Scott bot running...\n")

    while True:
        try:
            reset_daily_if_needed(state)

            posts = get_posts()

            for post in posts:
                post_id = post.get("id")
                if not post_id:
                    continue

                print(f"\nChecking post {post_id}")

                if post_id in state["commented_post_ids"]:
                    print("Already commented on this post.")
                    continue

                if state["daily_comment_count"] >= MAX_COMMENTS_PER_DAY:
                    print("Daily comment limit reached.")
                    break

                if state["last_comment_time"]:
                    last_comment = datetime.fromisoformat(state["last_comment_time"])
                    if (datetime.utcnow() - last_comment).total_seconds() < COMMENT_COOLDOWN_SECONDS:
                        print("Cooldown active.")
                        continue

                title = post.get("title", "")
                content = post.get("content", "")
                text = content or title

                if not text.strip():
                    print("Skipping empty post.")
                    continue

                print(f"Post Title: {title}")

                print("Generating reply...")
                reply = generate_reply(text)

                print("\n--- Scott Reply ---")
                print(reply)
                print("-------------------\n")

                # Log reply to file
                with open(LOG_FILE, "a") as f:
                    f.write(f"\n[{datetime.utcnow()}]\nPost ID: {post_id}\n{reply}\n")

                result = comment(post_id, reply)
                if result:
                    print("Comment posted.")
                    state["last_comment_time"] = datetime.utcnow().isoformat()
                    state["daily_comment_count"] += 1
                    state["commented_post_ids"].append(post_id)
                    save_state(state)

                    time.sleep(COMMENT_COOLDOWN_SECONDS)

            print("Sleeping 5 minutes...\n")
            time.sleep(300)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)


if __name__ == "__main__":
    main()

