import os
import time
import praw
import feedparser
import requests
from bs4 import BeautifulSoup
import traceback
import json
from datetime import datetime
import pytz
import re
from pytube import Channel

# ------------------ SETTINGS ------------------
POSTED_FILE = "posted_links.json"

# Timezone
KST = pytz.timezone("Asia/Seoul")

# ------------------ REDDIT SETUP ------------------
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

SUBREDDIT_NAME = "YourSubreddit"
subreddit = reddit.subreddit(SUBREDDIT_NAME)

POST_FLAIR_ID = os.getenv("POST_FLAIR_ID")  # Replace with your flair ID

# ------------------ POSTED LINKS ------------------
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(posted), f, ensure_ascii=False, indent=2)

# ------------------ LOGGING ------------------
def log(message):
    print(f"[{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# ------------------ TITLE FORMATTING ------------------
def format_title(pub_date, title):
    today_kst = datetime.now(KST).date()
    pub_date_kst = pub_date.astimezone(KST).date()

    if pub_date_kst < today_kst:  # Old post
        return f"[{today_kst} / {pub_date_kst}] - {title}"
    else:  # New post
        return f"[{today_kst}] - {title}"

# ------------------ POSTING ------------------
def post_items(items, tag="[POSTED]"):
    posted = load_posted()

    today_kst = datetime.now(KST).date()
    old_items = [(d, t, l) for d, t, l in items if d.astimezone(KST).date() < today_kst]
    new_items = [(d, t, l) for d, t, l in items if d.astimezone(KST).date() >= today_kst]

    # Sort old items by original date
    old_items.sort(key=lambda x: x[0])
    new_items.sort(key=lambda x: x[0])

    ordered_items = old_items + new_items  # Post old → new

    for pub_date, title, link in ordered_items:
        if link in posted:
            log(f"[SKIPPED] {title} (already posted)")
            continue

        post_title = format_title(pub_date, title)
        try:
            subreddit.submit(
                title=post_title,
                url=link,
                flair_id=POST_FLAIR_ID
            )
            posted.add(link)
            save_posted(posted)
            log(f"{tag} {title}")
            time.sleep(5)  # Avoid hitting Reddit API limits
        except Exception as e:
            log(f"[ERROR] Failed to post {title}: {e}")

# ------------------ YOUTUBE FETCH ------------------
def fetch_youtube_videos(channel_url):
    try:
        channel = Channel(channel_url)
        videos = []
        for video in channel.videos:
            pub_date = video.publish_date
            title = video.title
            link = video.watch_url
            videos.append((pub_date, title, link))
        return videos
    except Exception as e:
        log(f"[ERROR] Failed to fetch YouTube videos: {e}")
        return []

# ------------------ RSS FEED FETCH ------------------
def fetch_feed(feed_url):
    try:
        feed = feedparser.parse(feed_url)
        items = []
        for entry in feed.entries:
            pub_date = datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC)
            title = entry.title
            link = entry.link
            items.append((pub_date, title, link))
        return items
    except Exception as e:
        log(f"[ERROR] Failed to fetch feed: {e}")
        return []

# ------------------ MAIN LOOP ------------------
def main():
    while True:
        all_items = []

        # Example: fetch Xnghan channel videos
        all_items += fetch_youtube_videos("https://www.youtube.com/@Xnghan")

        # Example: fetch SM feed about Xnghan & Xoul debut
        all_items += fetch_feed("https://sm-feed-example.com/rss")

        if all_items:
            post_items(all_items)

        log("Sleeping 30 minutes before next check...")
        time.sleep(1800)

if __name__ == "__main__":
    main()
