import os, re, requests, cloudscraper, time
from bs4 import BeautifulSoup

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260402" 
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
    for script in soup.find_all("script"):
        text = script.string or ""
        patterns = [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']
        for pattern in patterns:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: 
                    movies.add(match.strip())
    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow"}
    return {m for m in movies if m.lower() not in noise and len(m) > 3}

def main():
    print(f"--- STARTING STEALTH CHECK ---")
    
    # Load history
    known = set()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            known = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(known)} movies from history.")

    # Stealth Scraper Configuration
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    success = False
    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1}...")
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1'
            }
            resp = scraper.get(THEATRE_URL, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                current = extract_movies(resp.text)
                print(f"Found on page: {current}")
                
                new_items = current - known
                
                # Always save state to keep file in sync
                with open(STATE_FILE, "w") as f:
                    f.write("\n".join(sorted(current)))
                
                if new_items and len(known) > 0:
                    msg = f"🎬 *New Show Added!*\n\n" + "\n".join([f"• {m}" for m in new_items])
                    send_telegram(msg)
                    print("Telegram alert sent!")
                
                success = True
                print("Check completed successfully.")
                break
            else:
                print(f"Failed with Status {resp.status_code}. Retrying...")
                time.sleep(5)
        except Exception as e:
            print(f"Error on attempt {attempt+1}: {e}")
            time.sleep(5)

    if not success:
        print("Could not bypass Cloudflare after 3 attempts.")

if __name__ == "__main__":
    main()
