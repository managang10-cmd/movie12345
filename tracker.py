import os, re, requests, cloudscraper, time, json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260402" 

# Multiple Theatres Configuration
THEATRES = [
    {
        "name": "Allu Cinemas - Kokapet",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}",
        "state_file": "known_movies_allu.txt"
    },
    {
        "name": "Prasads Imax",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/prasads-multiplex-hyderabad/buytickets/PRHN/{CHECK_DATE}",
        "state_file": "known_movies_imax.txt"
    },
    # Add more theatres like this:
    {
        "name": "ART Cinemas",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/art-cinemas-vanasthalipuram/buytickets/ACEV/{CHECK_DATE}",
        "state_file": "known_movies_art.txt"
    }
]

# Multiple Bot Configurations
TELEGRAM_CONFIGS = [
    {"bot_token": os.getenv("BOT_TOKEN"), "chat_id": os.getenv("CHAT_ID")},
    {"bot_token": os.getenv("BOT_TOKEN_2"), "chat_id": os.getenv("CHAT_ID_2")},
    {"bot_token": os.getenv("BOT_TOKEN_3"), "chat_id": os.getenv("CHAT_ID_3")},
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

def extract_movies_with_timings(html):
    """Extract movie titles and their timings"""
    soup = BeautifulSoup(html, "html.parser")
    movies_data = {}  # {movie_name: [timings]}
    
    # Looking for movie titles and timings in common BMS structures
    for script in soup.find_all("script"):
        text = script.string or ""
        
        # Extract movie titles
        movie_pattern = r'"EventTitle"\s*:\s*"([^"]+)"'
        for match in re.findall(movie_pattern, text):
            if 2 < len(match) < 60:
                movie_name = match.strip()
                if movie_name not in movies_data:
                    movies_data[movie_name] = []
        
        # Extract timings (HH:MM format)
        timing_pattern = r'"showtime"\s*:\s*"(\d{2}:\d{2})"'
        for match in re.findall(timing_pattern, text):
            timing = match.strip()
    
    # Backup: Look for data attributes
    for item in soup.find_all(['div', 'a'], attrs={'data-event-title': True}):
        movie_name = item.get('data-event-title', '').strip()
        if movie_name and 2 < len(movie_name) < 60:
            if movie_name not in movies_data:
                movies_data[movie_name] = []
    
    # Filter noise
    noise = {"allu", "cinemas", "kokapet", "hyderabad", "bookmyshow", "pvr", "paradise"}
    filtered = {m: t for m, t in movies_data.items() 
                if m.lower() not in noise and len(m) > 2}
    
    return filtered

def main():
    print("--- STARTING STEALTH CHECK ---")
    print(f"🕐 Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Enhanced Stealth Scraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # Professional Headers
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

    # Check each theatre
    for theatre in THEATRES:
        print(f"\n🎭 Checking: {theatre['name']}")
        print(f"🔗 URL: {theatre['url']}\n")
        
        known = set()
        state_file = theatre['state_file']
        
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                known = set(line.strip() for line in f if line.strip())
            print(f"✓ Loaded {len(known)} movies from history.")

        success = False
        for attempt in range(3):
            try:
                print(f"  Attempt {attempt + 1}...")
                resp = scraper.get(theatre['url'], headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    current_movies = extract_movies_with_timings(resp.text)
                    current = set(current_movies.keys())
                    print(f"  ✓ Found {len(current)} movies")
                    
                    new_items = current - known
                    
                    # Update history file
                    with open(state_file, "w") as f:
                        f.write("\n".join(sorted(current)))
                    
                    if new_items:
                        timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                        msg = f"🎬 *NEW MOVIE ALERT!*\n"
                        msg += f"🏢 *Theatre:* {theatre['name']}\n"
                        msg += f"📅 *Date:* {timestamp}\n"
                        msg += f"🔗 *URL:* {theatre['url']}\n\n"
                        msg += "*New Movies:*\n"
                        
                        for movie in sorted(new_items):
                            msg += f"• {movie}\n"
                        
                        send_to_all_chats(msg)
                        print(f"  ✨ Alert sent for {len(new_items)} new movie(s)!")
                    else:
                        print(f"  ℹ️  No new movies.")
                    
                    success = True
                    break
                elif resp.status_code == 403:
                    print(f"  ⚠️  Blocked (403). Retrying with delay...")
                    time.sleep(10)
                else:
                    print(f"  ⚠️  Status {resp.status_code}. Retrying...")
                    time.sleep(5)
            except Exception as e:
                print(f"  ❌ Error: {e}")
                time.sleep(5)

        if not success:
            print(f"  ❌ Failed to scrape {theatre['name']}")
        
        # Delay between theatres
        time.sleep(3)

if __name__ == "__main__":
    main()
