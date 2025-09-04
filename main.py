import os
import time
import feedparser
import praw
import pytz
from datetime import datetime

# --- Reddit login ---
reddit = praw.Reddit(
    client_id=os.environ["REDDIT_CLIENT_ID"],
    client_secret=os.environ["REDDIT_CLIENT_SECRET"],
    user_agent=os.environ["REDDIT_USER_AGENT"],
    username=os.environ["REDDIT_USERNAME"],
    password=os.environ["REDDIT_PASSWORD"]
)

subreddit_name = "YOURSUBREDDIT"   # change to your subreddit
post_flair_id = "YOUR_FLAIR_ID"    # your news flair id

# --- Feeds to check ---
feeds = {
    "Soompi": "https://www.soompi.com/feed",
    "Billboard K-Town": "https://www.billboard.com/feed",
    "Kpopmap": "https://www.kpopmap.com/feed",
    "Seoulspace": "https://www.seoulspace.com/feed"
}

# --- Track seen posts ---
seen = set()

def get_kst_time(utc_time):
    kst = pytz.timezone("Asia/Seoul")
    return utc_time.astimezone(kst)

while True:
    for source, url in feeds.items():
        d = feedparser.parse(url)
        for entry in d.entries[:3]:  # check last 3 posts
            if entry.link not in seen:
                seen.add(entry.link)
                kst_time = get_kst_time(datetime.utcnow())
                title = f"{kst_time.strftime('%Y-%m-%d %I:%M %p')} KST - {entry.title}"

                reddit.subreddit(subreddit_name).submit(
                    title=title,
                    url=entry.link,
                    flair_id=post_flair_id
                )
                print(f"Posted: {title}")

    time.sleep(300)  # wait 5 minutes
