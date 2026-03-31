import os, re, requests, cloudscraper
from bs4 import BeautifulSoup

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260402" # Target Date (Tomorrow)
THEATRE_URL = f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}"
STATE_FILE  = "known_movies.txt"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Telegram error: {e}")

def extract_movies(html):
    soup = BeautifulSoup(html, "html.parser")
    movies = set()
    # Look for movie titles in scripts (where BMS hides data)
    for script in soup.find_all("script"):
        text = script.string or ""
        patterns = [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']
        for pattern in patterns:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: 
                    movies.add(match.strip())
    # Clean out non-movie words
    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow", "generic"}
    return {m for m in movies if m.lower() not in noise and len(m) > 3}

def main():
    print(f"--- STARTING CHECK: {THEATRE_URL} ---")
    
    # 1. Load what we already knew
    known = set()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            known = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(known)} movies from history.")
    else:
        print("First run: No history file found yet.")

    # 2. Scrape the page
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    try:
        resp = scraper.get(THEATRE_URL, timeout=30)
        if resp.status_code == 200:
            current = extract_movies(resp.text)
            print(f"Found on page: {current}")

            # 3. Logic: Find New Items
            new_items = current - known
            
            # 4. Save state ALWAYS so the file stays updated
            with open(STATE_FILE, "w") as f:
                f.write("\n".join(sorted(current)))
            
            # 5. Notify if there's something new
            if new_items:
                print(f"New shows discovered: {new_items}")
                # Only alert if we already had a history (prevents 1st run spam)
                if len(known) > 0:
                    msg = f"🎬 *New Show Added at Allu Cinemas!*\n\n" + "\n".join([f"• {m}" for m in new_items])
                    send_telegram(msg)
                    print("Telegram alert sent!")
                else:
                    print("First run detected. History saved, no alert sent.")
            else:
                print("No new movies found since last check.")
        else:
            print(f"Failed to fetch BMS. Status: {resp.status_code}")

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
