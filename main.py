import os
import json
import time
from datetime import datetime, timezone
import pytz
import feedparser
from googleapiclient.discovery import build
import praw

# ------------------ SETTINGS ------------------
SUBREDDIT = os.getenv("SUBREDDIT", "XnghanAndXoul")
POST_FLAIR_ID = os.getenv("POST_FLAIR_ID")
POSTED_FILE = "posted_links.json"
TIMEZONE = pytz.timezone("Asia/Seoul")

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
    return json.load(open(POSTED_FILE, "r", encoding="utf-8")) if os.path.exists(POSTED_FILE) else []


def save_posted(posted):
    json.dump(posted, open(POSTED_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def format_title(title: str, original_dt: datetime) -> str:
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    orig_date = original_dt.astimezone(TIMEZONE).strftime("%Y-%m-%d")
    return f"[{today} / {orig_date}] - {title}" if orig_date < today else f"[{today}] - {title}"


def fetch_youtube_videos(channel_id: str):
    videos, token = [], None
    while True:
        res = youtube.search().list(
            part="snippet", channelId=channel_id, maxResults=50, order="date",
            type="video", pageToken=token
        ).execute()
        for i in res.get("items", []):
            title = i["snippet"]["title"]
            if not contains_keyword(title):
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
        if not contains_keyword(e.title):
            continue
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
    channels = ["UCMqkl3MPfMH1JWQhwmdfkSw", "UC9GtSLeksfK4yuJ_g1lgQbg"]

    while True:
        all_posts = []

        # gather everything
        for ch in channels:
            all_posts += fetch_youtube_videos(ch)
        all_posts += fetch_weverse_feed()

        # oldest first
        all_posts.sort(key=lambda x: x["date"])

        # catch up on missing posts
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
