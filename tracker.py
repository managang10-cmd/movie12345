import os, re, requests, cloudscraper, time, json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260402" 
THEATRE_URL = f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}"
STATE_FILE  = "known_movies.txt"

# Multiple Bot Configurations
TELEGRAM_CONFIGS = [
    {"bot_token": os.getenv("BOT_TOKEN_1"), "chat_id": os.getenv("CHAT_ID_1")},
    {"bot_token": os.getenv("BOT_TOKEN_2"), "chat_id": os.getenv("CHAT_ID_2")},
    {"bot_token": os.getenv("BOT_TOKEN_3"), "chat_id": os.getenv("CHAT_ID_3")},
    # Add more as needed
]

def send_telegram(msg, bot_token, chat_id):
    """Send message to a specific bot and chat"""
    if not bot_token or not chat_id:
        print(f"⚠️  Skipping - Missing credentials")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"✅ Bot {bot_token[:10]}... → Chat {chat_id}: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Bot Error: {e}")
        return False

def send_to_all_chats(msg):
    """Send message to all configured bots/chats in parallel"""
    print(f"\n📤 Sending to {len(TELEGRAM_CONFIGS)} destinations...")
    
    with ThreadPoolExecutor(max_workers=len(TELEGRAM_CONFIGS)) as executor:
        futures = [
            executor.submit(send_telegram, msg, config["bot_token"], config["chat_id"])
            for config in TELEGRAM_CONFIGS if config["bot_token"] and config["chat_id"]
        ]
        results = [f.result() for f in futures]
    
    success_count = sum(results)
    print(f"✨ Successfully sent to {success_count}/{len(results)} destinations")
    return success_count > 0

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
                    send_to_all_chats(msg)  # Send to all bots/chats
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
