import os, re, time, requests, cloudscraper
from bs4 import BeautifulSoup

# Config
CHECK_DATE = "20260401"
THEATRE_URL = f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}"
STATE_FILE = "known_movies.txt"

# Get sensitive info from GitHub Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def extract_movies(html):
    soup = BeautifulSoup(html, "html.parser")
    movies = set()
    for script in soup.find_all("script"):
        text = script.string or ""
        for pattern in [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: movies.add(match.strip())
    return {m for m in movies if len(m) > 3 and "allu" not in m.lower()}

# Main logic for a single run
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
resp = scraper.get(THEATRE_URL)
# ... inside your main logic ...
if resp.status_code == 200:
    current = extract_movies(resp.text)
    
    # Ensure current is at least an empty set so the file can be created
    if not current:
        current = set()

    # Save the state immediately to ensure the file exists for Git
    with open(STATE_FILE, "w") as f:
        f.write("\n".join(sorted(current)))
    
    # Now check for new items to send the alert
    new_items = current - known
    if new_items:
        send_telegram(f"🎬 *New Shows!* \n" + "\n".join(new_items))
