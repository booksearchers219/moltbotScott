#!/usr/bin/env python3
import os
import time
import json
import requests
import re
from datetime import datetime

API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY")

if not API_KEY:
    print("❌ ERROR: MOLTBOOK_API_KEY not set.")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

STATE_FILE = "scott_state.json"

# ===== SETTINGS =====
#COMMENT_COOLDOWN_SECONDS = 0
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
# AUTO VERIFICATION
# ===============================

def auto_verify_if_needed(response_json):
    try:
        comment_data = response_json.get("comment", {})
        if comment_data.get("verificationStatus") != "pending":
            return

        verification = comment_data.get("verification", {})
        challenge_text = verification.get("challenge_text", "")
        verification_code = verification.get("verification_code")

        if not verification_code:
            print("⚠️ No verification code found.")
            return

        print("🧠 Verification challenge detected.")
        print("   Raw challenge:", challenge_text)

        text = challenge_text.lower()

        word_to_number = {
            "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
            "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,
            "sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19,
            "twenty":20,"thirty":30,"forty":40,"fifty":50,
            "sixty":60,"seventy":70,"eighty":80,"ninety":90
        }

        for word, num in word_to_number.items():
            text = re.sub(rf"\b{word}\b", str(num), text)

        numbers = re.findall(r"\d+", text)
        numbers = [int(n) for n in numbers]

        if len(numbers) < 2:
            print("⚠️ Not enough numbers detected.")
            return

        # Operator detection
        if "*" in text or "times" in text or " x " in text:
            answer = numbers[0] * numbers[1]
            operation = "multiply"
        elif "minus" in text or "-" in text:
            answer = numbers[0] - numbers[1]
            operation = "subtract"
        else:
            answer = sum(numbers)
            operation = "add"

        formatted_answer = f"{answer:.2f}"

        print(f"🧠 Operation: {operation}")
        print(f"🧠 Solved: {numbers} → {formatted_answer}")

        for attempt in range(3):
            try:
                verify_response = requests.post(
                    f"{API_BASE}/verify",
                    headers=HEADERS,
                    json={
                        "verification_code": verification_code,
                        "answer": formatted_answer
                    },
                    timeout=10,
                )

                print("🔎 Verify status:", verify_response.status_code)
                print("🔎 Verify response:", verify_response.text)

                if verify_response.status_code == 200:
                    print("✅ Verification successful.")
                    return
                elif verify_response.status_code in (410, 409):
                    print("⚠️ Challenge expired or already answered.")
                    return

            except Exception as e:
                print(f"⚠️ Verify attempt {attempt+1} error:", e)

        print("❌ Verification failed after retries.")

    except Exception as e:
        print("⚠️ Auto verification error:", e)

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
        data = r.json()

        if not isinstance(data, dict):
            print("⚠️ Feed returned non-dict response.")
            return None

        if "posts" not in data or not isinstance(data["posts"], list):
            print("⚠️ Feed missing 'posts' list.")
            return None

        return data

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

        if r.status_code == 403:
            try:
                data = r.json()
                print("🚫 403 Response:", data.get("message"))
            except:
                print("🚫 403 Forbidden")
            return None

        r.raise_for_status()
        return r.json()

    except Exception as e:
        print("⚠️ Comment error:", e)
        return None


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
# HEARTBEAT LOOP
# ===============================

print("\n==============================")
print("💓 HEARTBEAT:", datetime.utcnow())
print("==============================")

state = load_state()

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

if feed:
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
        unseen_posts.reverse()

        for post in unseen_posts:
            post_id = post.get("id")
            author = post.get("author", {}).get("username", "unknown")
            title = post.get("title", "")
            content = post.get("content", "")
            submolt = post.get("submolt", {}).get("slug", "unknown")
            created = post.get("createdAt", "unknown")

            print("\n" + "=" * 60)
            print("📄 NEW POST DETECTED")
            print("=" * 60)
            print("🆔 ID:", post_id)
            print("👤 Author:", author)
            print("📚 Submolt:", submolt)
            print("🕒 Created:", created)

            if title:
                print("\n📌 Title:")
                print(title)

            print("\n📝 Content:")
            print(content)
            print("=" * 60 + "\n")

            state["last_seen_post_id"] = post_id
            save_state(state)

            reply_text = "Interesting perspective."

            if not DRY_RUN and can_post:
                result = comment(post_id, reply_text)
                if result:
                    print("✅ Comment posted.")

                    # AUTO VERIFY HERE
                    auto_verify_if_needed(result)

                    state["last_comment_time"] = time.time()
                    state["comments_today"] += 1
                    save_state(state)

                    break
                else:
                    print("⚠️ Comment failed.")
                    break
            else:
                print("🧪 DRY RUN or safety prevented posting.")

else:
    print("⚠️ No posts available.")

print("\n✅ Single run complete. Exiting.")

