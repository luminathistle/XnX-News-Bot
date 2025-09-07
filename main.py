import os
import time
import praw
import feedparser
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import pytz
import re
from pytube import Channel

# ------------------ SETTINGS ------------------
POSTED_FILE = "posted_links.json"

# ------------------ KEYWORDS ------------------
MAIN_KEYWORDS_EN = [
    "xnghan", "xoul",
    "xnghan&xoul", "xnghan & xoul", "xnghan and xoul",
    "xnghanxoul", "xnghan+xoul",
    "seunghan"
]
MAIN_KEYWORDS_HANGUL = [
    "엑스한", "서울", "승한", "승한앤소울"
]

def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", text.lower())

def contains_main_keyword(text: str) -> bool:
    if not text:
        return False
    text_norm = normalize(text)
    for kw in MAIN_KEYWORDS_EN:
        if normalize(kw) in text_norm:
            return True
    for kw in MAIN_KEYWORDS_HANGUL:
        if kw in text:
            return True
    return False

# ------------------ SOURCES ------------------
XNGHAN_CHANNEL_URL = "https://www.youtube.com/channel/UCMqkl3MPfMH1JWQhwmdfkSw"
SMTOWN_CHANNEL_URL = "https://www.youtube.com/channel/UCEf_Bc-KVd7onSeifS3py9g"

FEEDS = [
    ("https://www.soompi.com/feed", None, "Soompi"),
    ("https://www.billboard.com/pro/k-pop/", "h3 a", "Billboard K-Town"),
    ("https://www.koreatimes.co.kr/www/rss/entertainment.xml", None, "Korea Times Entertainment"),
    ("https://weverse.io/xnghanandxoul/feed", None, "Weverse - Notices"),
    ("https://weverse.io/xnghanandxoul/media", None, "Weverse - Media"),
    ("https://musicbutler.io/rss/artist/XnghanXoul", None, "MusicButler"),
]

# ------------------ FILE STORAGE ------------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            log(f"[WARN] Failed to load posted links: {e}")
    return set()

def save_posted(posted):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted), f)
    except Exception as e:
        log(f"[ERROR] Failed to save posted links: {e}")

# ------------------ DATE HANDLING ------------------
KST = pytz.timezone("Asia/Seoul")

def parse_date(entry, link=None):
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
    today_kst = datetime.now(KST).date()
    if not pub_date:
        return f"{today_kst.isoformat()} - {title}"
    pub_date_kst = pub_date.astimezone(KST).date()
    if pub_date_kst == today_kst:
        return f"{today_kst.isoformat()} - {title}"
    else:
        return f"{today_kst.isoformat()} / {pub_date_kst.isoformat()} - {title}"

# ------------------ LOGGING ------------------
def get_log_file():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    return f"bot-{today}.log"

def log(msg):
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{now}] {msg}"
    print(full_msg)
    try:
        with open(get_log_file(), "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except Exception as e:
        print(f"[WARN] Failed to write log file: {e}")

# ------------------ REDDIT AUTH ------------------
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT", "XnX-News-Bot"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
)

SUBREDDIT_NAME = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_ID = os.getenv("POST_FLAIR_ID")
subreddit = reddit.subreddit(SUBREDDIT_NAME)

# ------------------ YOUTUBE FETCH ------------------
def fetch_youtube_channel_videos(channel_url):
    try:
        ch = Channel(channel_url)
        videos = []
        for vid in ch.videos:
            if contains_main_keyword(vid.title):
                videos.append({
                    "title": vid.title,
                    "url": vid.watch_url,
                    "date": vid.publish_date or datetime.now(pytz.utc)
                })
        return videos
    except Exception as e:
        log(f"[ERROR] Failed to fetch YouTube channel {channel_url}: {e}")
        return []

# ------------------ FEED FETCH ------------------
def fetch_feed(feed_url, selector=None):
    try:
        if selector:  # HTML page
            r = requests.get(feed_url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            return [(a.get("href"), a.get_text(), None) for a in soup.select(selector)]
        else:  # RSS
            feed = feedparser.parse(feed_url)
            return [(entry.link, entry.title, entry) for entry in feed.entries]
    except Exception as e:
        log(f"[ERROR] Failed to fetch feed {feed_url}: {e}")
        return []

# ------------------ MAIN POSTER ------------------
def collect_all_items():
    all_items = []

    # YouTube: XngHan & SMTOWN
    for url in [XNGHAN_CHANNEL_URL, SMTOWN_CHANNEL_URL]:
        for vid in fetch_youtube_channel_videos(url):
            all_items.append((vid["date"], vid["title"], vid["url"]))

    # Feeds
    for feed_url, selector, source in FEEDS:
        items = fetch_feed(feed_url, selector)
        for link, title, entry in items:
            if not contains_main_keyword(title):
                log(f"[SKIPPED] {title} (no keyword)")
                continue
            pub_date = parse_date(entry, link) if entry else None
            all_items.append((pub_date or datetime.now(pytz.utc), title, link))

    # sort oldest → newest
    all_items.sort(key=lambda x: x[0])
    return all_items

def post_all():
    posted = load_posted()
    items = collect_all_items()

    for pub_date, title, link in items:
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
            log(f"[POSTED] {title}")
            time.sleep(5)
        except Exception as e:
            log(f"[ERROR] Failed to post {title}: {e}")

# ------------------ MAIN ------------------
if __name__ == "__main__":
    while True:
        log("Starting new cycle...")
        post_all()
        log("Cycle complete. Sleeping 60 seconds...\n")
        time.sleep(60)  # sleep 1 minute
