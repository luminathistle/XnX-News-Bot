import os
import time
import praw
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

# ======================
# Reddit authentication
# ======================
reddit = praw.Reddit(
    client_id=os.environ["REDDIT_CLIENT_ID"],
    client_secret=os.environ["REDDIT_CLIENT_SECRET"],
    username=os.environ["REDDIT_USERNAME"],
    password=os.environ["REDDIT_PASSWORD"],
    user_agent="multi-site-news-bot"
)

subreddit_name = os.environ["SUBREDDIT"]
flair_text = os.environ.get("FLAIR_TEXT", "MOD: Official News!")  # default if not set

# ======================
# Utility Functions
# ======================
def get_kst_time():
    return datetime.now(timezone.utc) + timedelta(hours=9)

def scrape_site(url, css_selector, site_name):
    """Scrape latest post title + link from a site."""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        post = soup.select_one(css_selector)
        if post:
            title = post.get_text(strip=True)
            link = post.get("href")
            if link and not link.startswith("http"):
                link = url.rstrip("/") + "/" + link.lstrip("/")
            return f"[{site_name}] {title}", link
    except Exception as e:
        print(f"Error scraping {site_name}: {e}")
    return None, None

def get_flair_id(subreddit, flair_text):
    """Find flair ID that matches the flair text."""
    for template in subreddit.flair.link_templates:
        if template["text"] == flair_text:
            return template["id"]
    raise ValueError(f"Flair '{flair_text}' not found in subreddit '{subreddit.display_name}'")

# ======================
# Scraping Sources
# ======================
sources = [
    ("https://www.soompi.com", "h6 a", "Soompi"),
    ("https://www.billboard.com/section/k-town", "h3 a", "Billboard K-Town"),
    ("https://www.kpopmap.com", "h3 a", "Kpopmap"),
    ("https://www.seoulspace.com", "h3 a", "SeoulSpace"),
]

# Track already posted links
posted_links = set()

# ======================
# Main Loop
# ======================
def main():
    subreddit = reddit.subreddit(subreddit_name)
    flair_id = get_flair_id(subreddit, flair_text)
    print(f"[INIT] Using flair: {flair_text} (id={flair_id})")

    while True:
        for url, selector, site_name in sources:
            title, link = scrape_site(url, selector, site_name)
            if title and link and link not in posted_links:
                try:
                    kst_time = get_kst_time().strftime("%Y-%m-%d %H:%M KST")
                    full_title = f"{title} | {kst_time}"
                    print(f"[POSTING] {full_title} -> {link}")

                    subreddit.submit(
                        title=full_title,
                        selftext=link,
                        flair_id=flair_id
                    )
                    posted_links.add(link)
                except Exception as e:
                    print(f"Error posting to Reddit: {e}")

        print("[WAIT] Sleeping 5 minutes...")
        time.sleep(300)  # 5 minutes


if __name__ == "__main__":
    main()
