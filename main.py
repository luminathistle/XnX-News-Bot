import os
import json
import time
from datetime import datetime, timezone
import pytz
import requests
import feedparser
from googleapiclient.discovery import build
import praw

# ------------------ SETTINGS ------------------
SUBREDDIT = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_ID = os.getenv("POST_FLAIR_ID")  # Reddit flair ID
START_DATE = datetime(2025, 9, 8, tzinfo=timezone.utc)  # Start date for bot
POSTED_FILE = "posted_links.json"

# ------------------ ENV VARS ------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ------------------ INITIALIZE ------------------
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
)

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# ------------------ HELPER FUNCTIONS ------------------
def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_posted(posted):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, indent=2, ensure_ascii=False)

def format_title(title, original_date):
    today = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d")
    if original_date.date() < datetime.now(pytz.timezone("Asia/Seoul")).date():
        orig = original_date.strftime("%Y-%m-%d")
        return f"[{today} / {orig}] - {title}"
    else:
        return f"[{today}] - {title}"

def fetch_youtube_videos(channel_id):
    videos = []
    next_page_token = None
    while True:
        res = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            maxResults=50,
            order="date",
            pageToken=next_page_token,
            type="video",
        ).execute()
        for item in res.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            published_at = datetime.fromisoformat(item["snippet"]["publishedAt"].replace("Z", "+00:00"))
            videos.append({
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "date": published_at
            })
        next_page_token = res.get("nextPageToken")
        if not next_page_token:
            break
    return sorted(videos, key=lambda x: x["date"])  # oldest first

def fetch_rss_articles(url):
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        articles.append({
            "url": entry.link,
            "title": entry.title,
            "date": published
        })
    return sorted(articles, key=lambda x: x["date"])  # oldest first

def post_to_reddit(post, posted):
    if post["url"] in posted:
        return
    title = format_title(post["title"], post["date"])
    submission = reddit.subreddit(SUBREDDIT).submit(title, url=post["url"], flair_id=POST_FLAIR_ID)
    print(f"Posted: {title}")
    posted.append(post["url"])
    save_posted(posted)

# ------------------ MAIN LOOP ------------------
def main():
    posted = load_posted()

    # ---- YouTube channels to monitor ----
    channels = [
        "CHANNEL_ID_XNGHAN",  # replace with actual channel ID
        "CHANNEL_ID_SM",      # replace with actual channel ID
    ]

    # ---- RSS feeds to monitor ----
    rss_feeds = [
        "https://example.com/feed.xml",  # replace with actual RSS URLs
    ]

    while True:
        all_posts = []

        # Fetch YouTube videos
        for channel in channels:
            videos = fetch_youtube_videos(channel)
            all_posts.extend(videos)

        # Fetch RSS articles
        for feed in rss_feeds:
            articles = fetch_rss_articles(feed)
            all_posts.extend(articles)

        # Sort all posts by date
        all_posts.sort(key=lambda x: x["date"])

        # Post in order
        for post in all_posts:
            post_to_reddit(post, posted)

        print("Sleeping 5 minutes...")
        time.sleep(300)  # 5 min

if __name__ == "__main__":
    main()
