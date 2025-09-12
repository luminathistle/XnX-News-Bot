import os
import json
import time
from datetime import datetime, timezone
import pytz
import feedparser
from googleapiclient.discovery import build
import praw
import requests

# ------------------ SETTINGS ------------------
SUBREDDIT = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_ID = os.getenv("POST_FLAIR_ID")
TIMEZONE = pytz.timezone("Asia/Seoul")

# GitHub backup settings
GITHUB_USER = os.getenv("GITHUB_USER")  # your GitHub username
GITHUB_REPO = os.getenv("GITHUB_REPO")  # repo to store posted_links.json
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # personal access token
POSTED_FILE = "posted_links.json"
GITHUB_FILE_PATH = "posted_links.json"

# ------------------ ENV VARS ------------------
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
)

youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_API_KEY"))

# ------------------ FILTER KEYS ------------------
KEYWORDS = ["xnghan", "xoul", "승한", "엑스한", "승한앤소울"]

def contains_keyword(text: str) -> bool:
    return any(k.lower() in text.lower() for k in KEYWORDS)

# ------------------ HELPERS ------------------
def load_posted():
    """Load posted links from GitHub or local file."""
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FILE_PATH}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            print("Loaded posted links from GitHub.")
            return r.json()
        else:
            print("GitHub file not found. Starting fresh.")
    except Exception as e:
        print("Error loading from GitHub:", e)
    
    # fallback to local file
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_posted(posted):
    """Save posted links locally and push to GitHub."""
    # Save locally
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, indent=2, ensure_ascii=False)
    
    # Push to GitHub
    try:
        import base64
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        
        # Get the SHA of the file if it exists
        r = requests.get(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}", headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None

        content = base64.b64encode(json.dumps(posted, ensure_ascii=False, indent=2).encode()).decode()
        data = {"message": "Update posted links", "content": content}
        if sha:
            data["sha"] = sha
        
        r = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}", headers=headers, json=data)
        if r.status_code in [200, 201]:
            print("Posted links backed up to GitHub.")
        else:
            print("Failed to backup to GitHub:", r.text)
    except Exception as e:
        print("Error saving to GitHub:", e)

def format_title(title: str, original_dt: datetime) -> str:
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    orig_date = original_dt.astimezone(TIMEZONE).strftime("%Y-%m-%d")
    return f"[{today} / {orig_date}] - {title}" if orig_date < today else f"[{today}] - {title}"

def fetch_youtube_videos(channel_id: str, filter_keywords=True):
    """Fetch videos from a YouTube channel. Only apply keywords filter if needed."""
    videos, token = [], None
    while True:
        res = youtube.search().list(
            part="snippet", channelId=channel_id, maxResults=50, order="date",
            type="video", pageToken=token
        ).execute()
        for i in res.get("items", []):
            title = i["snippet"]["title"]
            if filter_keywords and not contains_keyword(title):
                continue
            dt = datetime.fromisoformat(i["snippet"]["publishedAt"].replace("Z", "+00:00"))
            videos.append({
                "url": f"https://youtu.be/{i['id']['videoId']}",
                "title": title,
                "date": dt
            })
        token = res.get("nextPageToken")
        if not token:
            break
    return sorted(videos, key=lambda x: x["date"])

def fetch_weverse_feed():
    url = "https://weverse.io/xnghanandxoul/media/rss"
    feed = feedparser.parse(url)
    posts = []
    for e in feed.entries:
        dt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        posts.append({
            "url": e.link,
            "title": e.title,
            "date": dt
        })
    return sorted(posts, key=lambda x: x["date"])

def post_if_new(post, posted):
    if post["url"] in posted:
        return False
    title = format_title(post["title"], post["date"])
    reddit.subreddit(SUBREDDIT).submit(title, url=post["url"], flair_id=POST_FLAIR_ID)
    posted.append(post["url"])
    print("Posted:", title)
    return True

# ------------------ MAIN LOOP ------------------
def main():
    posted = load_posted()
    
    # Use SM’s channel for filtered keywords, XnX channel for everything
    sm_channel_id = "UCMqkl3MPfMH1JWQhwmdfkSw"  # SMTOWN
    xnx_channel_id = "UC9GtSLeksfK4yuJ_g1lgQbg" # XnX official
    
    while True:
        all_posts = []

        # Gather everything from XnX (no filter)
        all_posts += fetch_youtube_videos(xnx_channel_id, filter_keywords=False)
        # Gather SMTOWN but filter by keywords
        all_posts += fetch_youtube_videos(sm_channel_id, filter_keywords=True)
        # Add Weverse feed
        all_posts += fetch_weverse_feed()

        # Oldest first
        all_posts.sort(key=lambda x: x["date"])

        new_count = 0
        for post in all_posts:
            if post_if_new(post, posted):
                save_posted(posted)
                new_count += 1
                time.sleep(5)  # small delay to be safe

        if new_count == 0:
            print("No new posts. Sleeping 5 minutes…")
        else:
            print(f"Posted {new_count} new items. Sleeping 5 minutes…")

        time.sleep(300)

if __name__ == "__main__":
    main()
