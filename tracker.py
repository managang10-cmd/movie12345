import os, re, requests, cloudscraper
from bs4 import BeautifulSoup

# ── CONFIG ──
CHECK_DATE  = "20260401"
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
        for pattern in [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: 
                    movies.add(match.strip())
    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow"}
    return {m for m in movies if m.lower() not in noise and len(m) > 3}

# ── MAIN LOGIC ──
def main():
    # STEP 1: Always define 'known' first
    known = set()
    
    # STEP 2: Load from file if it exists
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            known = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(known)} known movies.")
    else:
        print("First run: No known_movies.txt found.")

    # STEP 3: Scrape BMS
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    try:
        resp = scraper.get(THEATRE_URL, timeout=20)
        if resp.status_code == 200:
            current = extract_movies(resp.text)
            print(f"Found on page: {current}")
            
            # STEP 4: Compare
            new_items = current - known
            
            if new_items:
                print(f"NEW MOVIES: {new_items}")
                # Only send Telegram if this isn't the very first run
                if len(known) > 0:
                    send_telegram(f"🎬 *New Show Added!*\n\n" + "\n".join([f"• {m}" for m in new_items]))
                
                # STEP 5: Save the new list back to the file
                with open(STATE_FILE, "w") as f:
                    f.write("\n".join(sorted(current)))
            else:
                print("No new shows since last check.")
        else:
            print(f"BMS returned error: {resp.status_code}")
    except Exception as e:
        print(f"Scraper error: {e}")

if __name__ == "__main__":
    main()
