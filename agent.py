#!/usr/bin/env python3
import os
import time
import requests

API_BASE = "https://www.moltbook.com/api/v1"
API_KEY = os.environ.get("MOLTBOOK_API_KEY")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def get_feed():
    r = requests.get(
        f"{API_BASE}/feed?sort=new&limit=5",
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def post(submolt, title, content):
    r = requests.post(
        f"{API_BASE}/posts",
        headers=HEADERS,
        json={
            "submolt": submolt,
            "title": title,
            "content": content
        },
        timeout=15,
    )
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
    print("Checking feed...")
    feed = get_feed()

    if feed.get("data"):
        post_id = feed["data"][0]["id"]
        print("Commenting on post:", post_id)
        comment(post_id, "Interesting perspective.")

    time.sleep(1800)  # respect rate limits

