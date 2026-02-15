#!/usr/bin/env python3
import os
import time
import json
import requests
from datetime import datetime

API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY")

if not API_KEY:
    print("❌ ERROR: MOLTBOOK_API_KEY not set.")
    exit(1)

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}

STATE_FILE = "scott_state.json"

# ===== SETTINGS =====
COMMENT_COOLDOWN_SECONDS = 60 * 60 * 4
MAX_COMMENTS_PER_DAY = 6
DRY_RUN = True
HEARTBEAT_INTERVAL = 600
SUBMOLTS_TO_SUBSCRIBE = ["security", "ai", "general"]
# ====================


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    return {
        "last_comment_time": 0,
        "comments_today": 0,
        "date": str(datetime.utcnow().date()),
        "last_seen_post_id": None,
        "subscribed_submolts": []
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ===============================
# SUBSCRIBE
# ===============================

def subscribe_to_submolt(slug):
    try:
        r = requests.post(
            f"{API_BASE}/submolts/{slug}/subscribe",
            headers=HEADERS,
            timeout=10,
        )

        if r.status_code in (200, 201):
            print(f"✅ Subscribed to {slug}")
        elif r.status_code == 409:
            print(f"ℹ️ Already subscribed (server): {slug}")
        elif r.status_code == 404:
            print(f"⚪ Submolt not found: {slug}")
        else:
            print(f"⚠️ Subscribe failed {slug}: {r.status_code}")

    except Exception as e:
        print(f"⚠️ Subscribe error for {slug}:", e)


# ===============================
# STARTUP SUB CHECK
# ===============================

state = load_state()

print("🔎 Checking submolt subscriptions...")

for sub in SUBMOLTS_TO_SUBSCRIBE:
    if sub not in state.get("subscribed_submolts", []):
        subscribe_to_submolt(sub)
        state.setdefault("subscribed_submolts", []).append(sub)
        save_state(state)
    else:
        print(f"ℹ️ Already recorded locally: {sub}")

print("✅ Subscription check complete.\n")


# ===============================
# API HELPERS
# ===============================

def get_feed():
    try:
        r = requests.get(
            f"{API_BASE}/posts?limit=10&sort=new",
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("⚠️ Feed error:", e)
        return None


def comment(post_id, content):
    try:
        r = requests.post(
            f"{API_BASE}/posts/{post_id}/comments",
            headers=HEADERS,
            json={"content": content},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("⚠️ Comment error:", e)
        return None


# ===============================
# HEARTBEAT LOOP
# ===============================

while True:
    print("\n==============================")
    print("💓 HEARTBEAT:", datetime.utcnow())
    print("==============================")

    state = load_state()

    # Reset daily comment count
    today = str(datetime.utcnow().date())
    if state["date"] != today:
        state["date"] = today
        state["comments_today"] = 0
        save_state(state)

    time_since_last = time.time() - state["last_comment_time"]
    can_post = (
        time_since_last >= COMMENT_COOLDOWN_SECONDS and
        state["comments_today"] < MAX_COMMENTS_PER_DAY
    )

    feed = get_feed()

    if feed and "posts" in feed and feed["posts"]:
        posts = feed["posts"]
        last_seen = state.get("last_seen_post_id")

        unseen_posts = []

        for post in posts:
            if post.get("id") == last_seen:
                break
            unseen_posts.append(post)

        if not unseen_posts:
            print("👀 No new posts.")
        else:
            print(f"📥 {len(unseen_posts)} new post(s) detected.")

            # Process oldest first
            unseen_posts.reverse()

            for post in unseen_posts:
                post_id = post.get("id")

                print("\n📄 Processing post:")
                print("   ID:", post_id)
                print("   Author:", post.get("author"))
                print("   Submolt:", post.get("submolt"))
                print("   Title:", post.get("title"))

                content = post.get("content", "")
                preview = content[:200] + ("..." if len(content) > 200 else "")
                print("   Content Preview:", preview)
                print("-" * 40)

                # Update last seen immediately
                state["last_seen_post_id"] = post_id
                save_state(state)

                reply_text = "Interesting perspective."

                if not DRY_RUN and can_post:
                    result = comment(post_id, reply_text)
                    if result:
                        print("✅ Comment posted.")
                        state["last_comment_time"] = time.time()
                        state["comments_today"] += 1
                        save_state(state)

                        # Recalculate cooldown
                        time_since_last = time.time() - state["last_comment_time"]
                        can_post = (
                            time_since_last >= COMMENT_COOLDOWN_SECONDS and
                            state["comments_today"] < MAX_COMMENTS_PER_DAY
                        )
                    else:
                        print("⚠️ Comment failed.")
                else:
                    print("🧪 DRY RUN or safety prevented posting.")
    else:
        print("No posts available.")

    print(f"\n😴 Sleeping {HEARTBEAT_INTERVAL} seconds...")
    time.sleep(HEARTBEAT_INTERVAL)

