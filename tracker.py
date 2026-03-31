import os, re, requests, cloudscraper
from bs4 import BeautifulSoup

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260401" # YYYYMMDD
THEATRE_URL = f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}"
STATE_FILE  = "known_movies.txt"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def extract_movies(html):
    soup = BeautifulSoup(html, "html.parser")
    movies = set()
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for movie titles in the JSON/Scripts
        for pattern in [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: 
                    movies.add(match.strip())
    # Filter out common noise
    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow"}
    return {m for m in movies if m.lower() not in noise and len(m) > 3}

# ── MAIN EXECUTION ───────────────────────
def main():
    # 1. Initialize 'known' so it ALWAYS exists
    known = set()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            known = set(line.strip() for line in f if line.strip())

    # 2. Scrape the site
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    try:
        resp = scraper.get(THEATRE_URL, timeout=20)
        if resp.status_code == 200:
            current = extract_movies(resp.text)
            
            # 3. Compare and Notify
            new_items = current - known
            if new_items:
                print(f"New shows found: {new_items}")
                send_telegram(f"🎬 *New Shows at Allu Cinemas!* \n\n" + "\n".join([f"• {m}" for m in new_items]))
                
                # 4. Update the file with the new list
                with open(STATE_FILE, "w") as f:
                    f.write("\n".join(sorted(current)))
            else:
                print("No new shows.")
        else:
            print(f"Failed to fetch BMS: Status {resp.status_code}")
    except Exception as e:
        print(f"Scraper error: {e}")

if __name__ == "__main__":
    main()
