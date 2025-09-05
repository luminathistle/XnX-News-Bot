import os
import time
import praw
import feedparser
import requests
from bs4 import BeautifulSoup

# -------------------------
# Reddit authentication
# -------------------------
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent="XnX-News-Bot",
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD")
)

SUBREDDIT_NAME = "XnghanAndXoul"  # <-- change this to your subreddit name
POST_FLAIR_TEXT = "MOD: Official News!"  # flair text
KEYWORDS = ["xnghan", "xoul", "seunghan", "xnghan&xoul"]

# -------------------------
# Feeds setup
# -------------------------
FEEDS = [
    ("https://www.soompi.com/feed", None, "Soompi"),
    ("https://www.billboard.com/pro/k-pop/", "h3 a", "Billboard K-Town"),
    ("https://www.kpopmap.com/feed/", None, "Kpopmap"),
    ("https://www.seoulspace.com/feed/", None, "SeoulSpace"),
]

# -------------------------
# Helper functions
# -------------------------

def get_rss_articles(url):
    """Parse RSS feed and return (title, link) list."""
    feed = feedparser.parse(url)
    return [(entry.title, entry.link) for entry in feed.entries]

def scrape_billboard(url, selector):
    """Scrape Billboard page headlines since RSS is dead."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        for a in soup.select(selector):
            title = a.get_text(strip=True)
            link = a.get("href")
            if link and not link.startswith("http"):
                link = "https://www.billboard.com" + link
            articles.append((title, link))
        return articles
    except Exception as e:
        print("Error scraping Billboard:", e)
        return []

def matches_keywords(title):
    """Check if title contains any of our keywords."""
    return any(k in title.lower() for k in KEYWORDS)

def get_flair_id(subreddit, flair_text):
    """Fetch the flair ID for the given text."""
    for flair in subreddit.flair.link_templates:
        if flair["text"] == flair_text:
            return flair["id"]
    return None

# -------------------------
# Main loop
# -------------------------
def main():
    subreddit = reddit.subreddit(SUBREDDIT_NAME)
    flair_id = get_flair_id(subreddit, POST_FLAIR_TEXT)
    if not flair_id:
        print(f"[ERROR] Flair '{POST_FLAIR_TEXT}' not found in r/{SUBREDDIT_NAME}")
        return

    posted_links = set()

    while True:
        for url, selector, label in FEEDS:
            if selector:  # Billboard scrape
                articles = scrape_billboard(url, selector)
            else:  # RSS feeds
                articles = get_rss_articles(url)

            for title, link in articles:
    if link in posted_links:
        continue
    if not matches_keywords(title):
        print(f"[SKIP] {title}")
        continue

    try:
        submission = subreddit.submit(
            title=f"[{label}] {title}",
            url=link,
            flair_id=flair_id,
            resubmit=False
        )
        posted_links.add(link)

        # ✅ Extra confirmation
        print(f"[POSTED] {title} -> {submission.shortlink}")
        print(f"[FLAIR] Applied '{POST_FLAIR_TEXT}' to {submission.shortlink}")

    except Exception as e:
        print(f"[ERROR posting] {title} | {e}")

        print("Sleeping for 15 minutes...")
        time.sleep(900)

# -------------------------
# Run bot
# -------------------------
if __name__ == "__main__":
    main()
