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
        r = requests.post(url, json=payload, timeout=15)
        print(f"Telegram Response: {r.status_code}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def extract_movies(html):
    soup = BeautifulSoup(html, "html.parser")
    movies = set()
    # Looking for movie titles in common BMS structures
    for script in soup.find_all("script"):
        text = script.string or ""
        patterns = [r'"EventTitle"\s*:\s*"([^"]+)"', r'"movieName"\s*:\s*"([^"]+)"']
        for pattern in patterns:
            for match in re.findall(pattern, text):
                if 2 < len(match) < 60: 
                    movies.add(match.strip())
    
    # Backup: Look for standard links/titles if scripts are obfuscated
    for item in soup.find_all(['a', 'div'], attrs={'data-event-title': True}):
        movies.add(item['data-event-title'].strip())

    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow"}
    return {m for m in movies if m.lower() not in noise and len(m) > 2}

def main():
    print("--- STARTING STEALTH CHECK ---")
    
    known = set()
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            known = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(known)} movies from history.")

    # Enhanced Stealth Scraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Professional Headers to mimic a real Windows Chrome user
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://in.bookmyshow.com/',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1'
    }

    success = False
    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1}...")
            resp = scraper.get(THEATRE_URL, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                current = extract_movies(resp.text)
                print(f"Found on page: {current}")
                
                new_items = current - known
                
                # Update history file
                with open(STATE_FILE, "w") as f:
                    f.write("\n".join(sorted(current)))
                
                if new_items:
                    msg = f"🎬 *New Show Added!*\n\n" + "\n".join([f"• {m}" for m in new_items])
                    send_telegram(msg)
                    print(f"Alert sent!")
                else:
                    print("No new movies found.")
                
                success = True
                break
            elif resp.status_code == 403:
                print("BMS blocked us (403). Trying again with slight delay...")
                time.sleep(10)
            else:
                print(f"Status {resp.status_code}. Retrying...")
                time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

    if not success:
        print("Scrape failed. Cloudflare or BMS Firewall is high today.")

if __name__ == "__main__":
    main()
