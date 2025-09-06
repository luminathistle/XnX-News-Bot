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

# ------------------ SETTINGS ------------------

POSTED_FILE = "posted_links.json"

# ------------------ KEYWORDS ------------------

# English keywords (case-insensitive)
MAIN_KEYWORDS_EN = [
    "xnghan",
    "xoul",
    "xnghan & xoul",
    "xnghan and xoul",
    "seunghan"
]

# Hangul keywords (exact match)
MAIN_KEYWORDS_HANGUL = [
    "엑스한",
    "서울",
    "승한",
    "승한앤소울"
]

def contains_main_keyword(text: str) -> bool:
    """Return True if any MAIN_KEYWORDS appear in text."""
    if not text:
        return False
    text_lower = text.lower()
    for kw in MAIN_KEYWORDS_EN:
        if kw.lower() in text_lower:
            return True
    for kw in MAIN_KEYWORDS_HANGUL:
        if kw in text:
            return True
    return False

# ------------------ FEEDS ------------------

XNGHAN_CHANNEL_ID = "UCMqkl3MPfMH1JWQhwmdfkSw"
SMTOWN_CHANNEL_ID = "UCEf_Bc-KVd7onSeifS3py9g"

FEEDS = [
    ("https://www.soompi.com/feed", None, "Soompi"),
    ("https://www.billboard.com/pro/k-pop/", "h3 a", "Billboard K-Town"),
    ("https://www.koreatimes.co.kr/www/rss/entertainment.xml", None, "Korea Times Entertainment"),
    ("https://weverse.io/xnghanandxoul/feed", None, "Weverse - Notices"),
    ("https://weverse.io/xnghanandxoul/media", None, "Weverse - Media"),
    ("https://www.youtube.com/feeds/videos.xml?channel_id=" + XNGHAN_CHANNEL_ID, None, "YouTube - XngHan"),
    ("https://www.youtube.com/feeds/videos.xml?channel_id=" + SMTOWN_CHANNEL_ID, None, "YouTube - SMTOWN"),
    ("https://musicbutler.io/rss/artist/XnghanXoul", None, "MusicButler"),
]

# ------------------ FILE STORAGE ------------------

def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print("[WARN] Failed to load posted links:", e)
    return set()

def save_posted(posted):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted), f)
    except Exception as e:
        print("[ERROR] Failed to save posted links:", e)

# ------------------ DATE HANDLING ------------------

KST = pytz.timezone("Asia/Seoul")

def parse_date(entry, link=None):
    """Return datetime with tzinfo (KST fallback)."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
    if link:
        try:
            r = requests.get(link, timeout=5)
            soup = BeautifulSoup(r.text, "html.parser")
            meta = soup.find("meta", {"property": "article:published_time"})
            if meta and meta.get("content"):
                return datetime.fromisoformat(meta["content"].split("Z")[0]).replace(tzinfo=pytz.utc)
            time_tag = soup.find("time")
            if time_tag and time_tag.get("datetime"):
                return datetime.fromisoformat(time_tag["datetime"].split("Z")[0]).replace(tzinfo=pytz.utc)
        except Exception:
            pass
    return None

def format_title(pub_date, title):
    """Format post title with today / original date."""
    today_kst = datetime.now(KST).date()
    if not pub_date:
        return f"{today_kst.isoformat()} - [XNGHAN & XOUL] {title}"
    pub_date_kst = pub_date.astimezone(KST).date()
    if pub_date_kst == today_kst:
        return f"{today_kst.isoformat()} - [XNGHAN & XOUL] {title}"
    else:
        return f"{today_kst.isoformat()} / {pub_date_kst.isoformat()} - [XNGHAN & XOUL] {title}"

# ------------------ FILTERING ------------------

def is_relevant(entry):
    """Check if entry contains main keywords, including page fallback."""
    title = getattr(entry, "title", "") if hasattr(entry, "title") else entry.get("title", "")
    summary = getattr(entry, "summary", "") if hasattr(entry, "summary") else entry.get("summary", "")
    combined = f"{title}\n{summary}"
    if contains_main_keyword(combined):
        return True

    # fallback: fetch page text
    try:
        link = getattr(entry, "link", "") if hasattr(entry, "link") else entry.get("link", "")
        if link:
            page_text = requests.get(link, timeout=6, headers={"User-Agent": os.getenv("REDDIT_USER_AGENT", "XnX-News-Bot")}).text
            if contains_main_keyword(page_text):
                return True
    except Exception:
        pass
    return False

# ------------------ REDDIT AUTH ------------------

# Secret-only approach using environment variables
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT", "XnX-News-Bot"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
)

SUBREDDIT_NAME = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_TEXT = os.getenv("FLAIR_TEXT", "MOD: Official Updates!")

subreddit = reddit.subreddit(SUBREDDIT_NAME)

# ------------------ MAIN LOOP ------------------

def run_bot():
    posted = load_posted()

    for url, selector, source in FEEDS:
        try:
            # RSS/Youtube feeds
            if url.endswith(".xml") or "feed" in url or "rss" in url or "youtube" in url:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    if entry.link in posted:
                        continue
                    if not is_relevant(entry):
                        continue

                    pub_date = parse_date(entry, entry.link)

                    # Post old content too
                    post_title = format_title(pub_date, entry.title)
                    subreddit.submit(title=post_title, url=entry.link, flair_text=POST_FLAIR_TEXT)
                    posted.add(entry.link)
                    save_posted(posted)
                    print(f"[POSTED] {post_title} ({source})")
                    time.sleep(5)  # 5-second delay between posts

            # HTML feeds
            else:
                r = requests.get(url, timeout=5)
                soup = BeautifulSoup(r.text, "html.parser")
                items = soup.select(selector) if selector else []
                for a in items:
                    link = a.get("href")
                    title = a.get_text(strip=True)
                    if not link or link in posted:
                        continue
                    if not is_relevant({"title": title}):
                        continue

                    post_title = format_title(None, title)
                    subreddit.submit(title=post_title, url=link, flair_text=POST_FLAIR_TEXT)
                    posted.add(link)
                    save_posted(posted)
                    print(f"[POSTED] {post_title} ({source})")
                    time.sleep(5)  # 5-second delay between posts

        except Exception as e:
            print(f"[ERROR] {source}: {e}")
            traceback.print_exc()

# ------------------ RUN ------------------

if __name__ == "__main__":
    run_bot()
