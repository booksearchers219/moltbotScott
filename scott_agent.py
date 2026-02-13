#!/usr/bin/env python3
import os
import time
import json
import requests
from datetime import datetime

API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY")

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}



STATE_FILE = "scott_state.json"

# ===== SAFETY SETTINGS =====
COMMENT_COOLDOWN_SECONDS = 60 * 60 * 4   # 4 hours
MAX_COMMENTS_PER_DAY = 6                 # hard safety cap
DRY_RUN = True                           # True = DO NOT post publicly
# ===========================


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "last_comment_time": 0,
        "comments_today": 0,
        "date": str(datetime.utcnow().date())
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_feed():
    print("➡ Sending request to /posts...")
    r = requests.get(
        f"{API_BASE}/posts?limit=5",
        headers=HEADERS,
        timeout=10,
    )
    print("⬅ Response received. Status:", r.status_code)
    r.raise_for_status()
    return r.json()






def comment(post_id, content):
    r = requests.post(
        f"{API_BASE}/posts/{post_id}/comments",
        headers=HEADERS,
        json={"content": content},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


while True:
    print("\n🔍 Checking feed...")
    state = load_state()

    now = datetime.utcnow()
    today_str = str(now.date())

    # Reset daily counter if new day
    if state["date"] != today_str:
        state["date"] = today_str
        state["comments_today"] = 0

    time_since_last = time.time() - state["last_comment_time"]

    if time_since_last < COMMENT_COOLDOWN_SECONDS:
        print("⏳ 4-hour cooldown active.")
        can_post = False
    elif state["comments_today"] >= MAX_COMMENTS_PER_DAY:
        print("🚫 Daily limit reached.")
        can_post = False
    else:
        can_post = True

    # ALWAYS fetch feed (not inside else)
    feed = get_feed()
    print("DEBUG FULL RESPONSE:")
    print(feed)

    # Adjust depending on actual JSON structure
    if isinstance(feed, dict) and "posts" in feed and feed["posts"]:
        post_data = feed["posts"][0]
        post_id = post_data["id"]
        title = post_data.get("title", "")
        content = post_data.get("content", "")

        reply_text = "Interesting perspective."

        print("\n==============================")
        print("📥 Post Seen:")
        print("ID:", post_id)
        print("Title:", title)
        print("Content:", content)
        print("\n🤖 Bot Reply:")
        print(reply_text)
        print("==============================\n")

        if DRY_RUN:
            print("🧪 DRY RUN MODE — Not posting publicly.")
        else:
            if can_post:
                comment(post_id, reply_text)
                print("✅ Comment posted.")
                state["last_comment_time"] = time.time()
                state["comments_today"] += 1
                save_state(state)
            else:
                print("🚫 Skipped due to safety rules.")
    else:
        print("No posts found or unexpected JSON structure.")

    # Check feed every 10 minutes
    time.sleep(600)

