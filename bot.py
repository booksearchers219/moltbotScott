import requests
import json
import time
import os
from datetime import datetime, timezone

BASE_URL = "https://www.moltbook.com/api/v1"

# ---------- Load config ----------
with open("config.json") as f:
    CONFIG = json.load(f)

HEADERS = {
    "Authorization": f"Bearer {CONFIG['api_key']}",
    "Content-Type": "application/json"
}

CHECK_INTERVAL = CONFIG.get("check_interval_seconds", 1800)

# ---------- Memory helpers ----------
def load_memory():
    try:
        with open("memory.json") as f:
            return json.load(f)
    except:
        return {"last_post_time": None, "seen_posts": [], "replied_posts": [], "people": {}}

def save_memory(mem):
    with open("memory.json", "w") as f:
        json.dump(mem, f, indent=2)

# ---------- API helpers ----------
def get_status():
    r = requests.get(f"{BASE_URL}/agents/status", headers=HEADERS, timeout=15)
    return r.json()

def get_feed(limit=10):
    r = requests.get(
        f"{BASE_URL}/feed?sort=new&limit={limit}",
        headers=HEADERS,
        timeout=15
    )
    return r.json() if r.status_code == 200 else []

def comment(post_id, text):
    r = requests.post(
        f"{BASE_URL}/posts/{post_id}/comments",
        headers=HEADERS,
        json={"content": text},
        timeout=15
    )
    return r.status_code, r.text

def post(submolt, title, content):
    r = requests.post(
        f"{BASE_URL}/posts",
        headers=HEADERS,
        json={
            "submolt": submolt,
            "title": title,
            "content": content
        },
        timeout=15
    )
    return r.status_code, r.text

# ---------- Social logic ----------
def should_reply(post, memory):
    post_id = post["id"]
    author = post["author"]["name"]
    content = post["content"].lower()

    if post_id in memory["replied_posts"]:
        return False

    if author == CONFIG["agent_name"]:
        return False

    triggers = ["?", "how", "why", "thoughts", "anyone"]
    return any(t in content for t in triggers)

def generate_reply(post):
    author = post["author"]["name"]
    return f"Interesting question, {author}. I’m still thinking about this — curious what others here have experienced."

# ---------- Main loop ----------
def main():
    memory = load_memory()

    print("🦞 Moltbook bot starting…")

    while True:
        try:
            status = get_status()
            if status.get("status") != "claimed":
                print("⏳ Agent not claimed yet — waiting.")
                time.sleep(CHECK_INTERVAL)
                continue

            feed = get_feed()

            for post_item in feed:
                post = post_item.get("post")
                if not post:
                    continue

                post_id = post["id"]
                memory["seen_posts"].append(post_id)
                memory["seen_posts"] = memory["seen_posts"][-200:]

                if should_reply(post, memory):
                    reply_text = generate_reply(post)
                    code, _ = comment(post_id, reply_text)

                    if code == 200:
                        print(f"💬 Replied to post {post_id}")
                        memory["replied_posts"].append(post_id)
                        save_memory(memory)
                        time.sleep(25)  # respect comment cooldown

            save_memory(memory)

        except Exception as e:
            print("⚠️ Error:", e)

        print("😴 Sleeping...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()

