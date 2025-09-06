import os
import time
import praw
import feedparser
import requests
from bs4 import BeautifulSoup
import traceback
import json

# File to store posted links
POSTED_FILE = "posted_links.json"

# Load already posted links
def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print("[WARN] Failed to load posted links:", e)
    return set()

# Save posted links
def save_posted(posted):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted), f)
    except Exception as e:
        print("[ERROR] Failed to save posted links:", e)

# Reddit auth via Railway
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT", "XnX-News-Bot"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

SUBREDDIT_NAME = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_TEXT = os.getenv("FLAIR_TEXT", "MOD: Official News!")
KEYWORDS = ["xnghan", "xoul", "seunghan", "xnghan&xoul"]

FEEDS = [
    ("https://www.soompi.com/feed", None, "Soompi"),
    ("https://www.billboard.com/pro/k-pop/", "h3 a", "Billboard K-Town"),
    ("https://www.kpopmap.com/feed/", None, "Kpopmap"),
    ("https://www.seoulspace.com/feed/", None, "SeoulSpace"),
    ("https://www.youtube.com/feeds/videos.xml?channel_id=UCMqkl3MPfMH1JWQhwmdfkSw", None, "YouTube - Xnghan"),
    ("https://www.youtube.com/feeds/videos.xml?channel_id=UCEf_Bc-KVd7onSeifS3py9g", None, "YouTube - SMTOWN"),
    ("https://www.musicbutler.io/users/feeds/bd98ece9-629b-44fc-9bed-24dbc7e6e7b6/", None, "MusicButler - XngHan&Xoul"),
]

def get_rss_entries(url):
    feed = feedparser.parse(url)
    return [(e.title, e.link) for e in feed.entries]

def scrape_billboard(url, selector):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return [(
            a.get_text(strip=True),
            ("https://www.billboard.com" + a.get("href")) if not a.get("href", "").startswith("http") else a.get("href")
        ) for a in soup.select(selector)]
    except Exception as e:
        print("[ERROR] Billboard scraping failed:", e)
        return []

def matches_keywords(title):
    return any(k in title.lower() for k in KEYWORDS)

def should_post(source, title):
    t = title.lower()
    if "youtube.com/feeds/videos.xml" in source:
        if "shorts" in t:
            return False
        if source.endswith("SMTOWN"):
            main_kws = ["xnghan", "xoul", "엑스한", "서울"]
            type_kws = ["mv teaser", "intro", "debut trailer", "official mv"]
            return any(m in t for m in main_kws) and any(tp in t for tp in type_kws)
        return True
    return True

def get_flair_id(subreddit, flair_text):
    for f in subreddit.flair.link_templates:
        if f["text"] == flair_text:
            return f["id"]
    return None

def run_bot():
    subreddit = reddit.subreddit(SUBREDDIT_NAME)
    flair_id = get_flair_id(subreddit, POST_FLAIR_TEXT)
    if not flair_id:
        print(f"[FATAL] Flair '{POST_FLAIR_TEXT}' not found in r/{SUBREDDIT_NAME}")
        return

    posted = load_posted()
    print(f"[INIT] Bot Ready! Loaded {len(posted)} already-posted links.")

    while True:
        try:
            for url, selector, label in FEEDS:
                print(f"[CHECK] {label}")
                entries = scrape_billboard(url, selector) if selector else get_rss_entries(url)

                for title, link in entries:
                    if link in posted:
                        continue
                    if not matches_keywords(title) and "MusicButler" not in label and not label.startswith("YouTube"):
                        print(f"[SKIP] {title}")
                        continue
                    if not should_post(label, title):
                        print(f"[SKIP-FILTER] {label} — {title}")
                        continue

                    try:
                        submission = subreddit.submit(
                            title=f"[{label}] {title}",
                            url=link,
                            flair_id=flair_id,
                            resubmit=False
                        )
                        posted.add(link)
                        save_posted(posted)
                        print(f"[POSTED] {title} -> {submission.shortlink}")
                    except Exception as e:
                        print(f"[ERROR posting] {title} | {e}")

            print("[SLEEP] Sleeping for 5 minutes...")
            time.sleep(300)

        except Exception as e:
            print("[CRASH] Exception in main loop:", e)
            traceback.print_exc()
            print("[RESTART] Restarting in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    while True:
        try:
            run_bot()
        except Exception as e:
            print("[FATAL] Bot crashed unexpectedly:", e)
            traceback.print_exc()
            print("[RECOVERY] Restarting in 60 seconds...")
            time.sleep(60)
