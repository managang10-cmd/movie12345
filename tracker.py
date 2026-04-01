import os, re, requests, cloudscraper, time, json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── CONFIGURATION ────────────────────────
CHECK_DATE  = "20260403"

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
    {
        "name": "ART Cinemas",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/art-cinemas-vanasthalipuram/buytickets/ACEV/{CHECK_DATE}",
        "state_file": "known_movies_art.txt"
    }
]

TELEGRAM_CONFIGS = [
    {"bot_token": os.getenv("BOT_TOKEN"),   "chat_id": os.getenv("CHAT_ID")},
    {"bot_token": os.getenv("BOT_TOKEN_2"), "chat_id": os.getenv("CHAT_ID_2")},
    {"bot_token": os.getenv("BOT_TOKEN_3"), "chat_id": os.getenv("CHAT_ID_3")},
]


# ── Telegram ─────────────────────────────
def send_telegram(msg, bot_token, chat_id):
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"✅ Bot {bot_token[:10]}... → {chat_id}: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ {e}")
        return False


def send_to_all_chats(msg):
    valid = [c for c in TELEGRAM_CONFIGS if c["bot_token"] and c["chat_id"]]
    if not valid:
        print("⚠️  No Telegram credentials configured.")
        return
    with ThreadPoolExecutor(max_workers=len(valid)) as ex:
        results = list(ex.map(lambda c: send_telegram(msg, c["bot_token"], c["chat_id"]), valid))
    print(f"✨ Sent to {sum(results)}/{len(results)} destinations")


# ── Extraction ────────────────────────────
def extract_movies_with_timings(html):
    """
    Returns: { "Movie Name": ["10:30 AM", "1:15 PM", ...] }
    Searches both JSON script blobs and visible HTML elements.
    """
    soup = BeautifulSoup(html, "html.parser")
    movies = {}   # name -> set of timings

    def add(name, timing=None):
        name = name.strip()
        if not name or len(name) < 3 or len(name) > 80 or name.startswith("http"):
            return
        if name not in movies:
            movies[name] = set()
        if timing:
            movies[name].add(timing.strip().upper())

    time_re = re.compile(r'\b(1[0-2]|0?[1-9]):[0-5]\d\s*(?:AM|PM)\b', re.I)

    # ── 1. JSON inside <script> tags ──────
    for script in soup.find_all("script"):
        raw = script.string or ""
        if not raw.strip():
            continue

        # Find all JSON objects in the script
        for chunk in re.finditer(r'\{[^{}]{10,}\}', raw):
            try:
                obj = json.loads(chunk.group())
                title = (obj.get("EventTitle") or obj.get("movieName") or
                         obj.get("movieTitle") or obj.get("title") or "")
                timing = (obj.get("showtime") or obj.get("ShowTime") or
                          obj.get("show_time") or obj.get("startTime") or "")
                if title:
                    add(title, timing if timing else None)
            except Exception:
                pass

        # Line-by-line: pair movie names with times on nearby lines
        last_movie = None
        for line in raw.splitlines():
            for pat in [r'"EventTitle"\s*:\s*"([^"]+)"',
                        r'"movieName"\s*:\s*"([^"]+)"',
                        r'"movieTitle"\s*:\s*"([^"]+)"']:
                m = re.search(pat, line)
                if m:
                    last_movie = m.group(1).strip()
                    add(last_movie)
            for t in time_re.findall(line):
                if last_movie:
                    add(last_movie, t)

    # ── 2. Visible HTML blocks ────────────
    for block in soup.find_all(["div", "li", "article"],
                               class_=re.compile(r'movie|show|event|film', re.I)):
        # Movie name
        title_tag = block.find(class_=re.compile(r'title|name|heading', re.I))
        name = title_tag.get_text(strip=True) if title_tag else (
            block.get("data-event-title") or block.get("data-movie-name") or "")
        if name:
            add(name)
            # Timings inside the same block
            for t_tag in block.find_all(class_=re.compile(r'time|slot|show', re.I)):
                for t in time_re.findall(t_tag.get_text()):
                    add(name, t)

    # ── 3. Clean noise ────────────────────
    noise = {"bookmyshow","movies","hyderabad","book","shows","cinema","select",
             "language","date","filter","sort","home","back","allu","cinemas",
             "kokapet","ok","cancel","apply","clear","pvr","paradise","imax","prasads"}

    return {name: sorted(times)
            for name, times in movies.items()
            if name.lower() not in noise}


# ── State file helpers ────────────────────
def load_state(path):
    """Returns {movie: [timings]} or None if first run."""
    if not os.path.exists(path):
        return None
    data = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                name, times_str = line.split("|", 1)
                data[name] = [t for t in times_str.split(",") if t]
            else:
                data[line] = []
    return data


def save_state(path, movies):
    with open(path, "w") as f:
        for name, timings in sorted(movies.items()):
            f.write(f"{name}|{','.join(sorted(timings))}\n")


# ── Alert message builder ─────────────────
def build_alert(theatre_name, theatre_url, new_movies, new_timings):
    ts  = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    msg = f"🎬 *NEW SHOW ALERT!*\n"
    msg += f"🏢 *Theatre:* {theatre_name}\n"
    msg += f"📅 *At:* {ts}\n"
    msg += f"🔗 [Book Now]({theatre_url})\n"

    if new_movies:
        msg += "\n*🆕 New Movies Added:*\n"
        for movie, timings in sorted(new_movies.items()):
            if timings:
                msg += f"• *{movie}*\n  🕐 {' | '.join(timings)}\n"
            else:
                msg += f"• *{movie}* — open BMS to see timings\n"

    if new_timings:
        msg += "\n*🕐 New Show Times for Existing Movies:*\n"
        for movie, timings in sorted(new_timings.items()):
            msg += f"• *{movie}*\n  ➕ {' | '.join(timings)}\n"

    return msg


# ── Main ──────────────────────────────────
def main():
    print("--- BMS SHOW TRACKER ---")
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    headers = {
        "User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language":           "en-US,en;q=0.9",
        "Referer":                   "https://in.bookmyshow.com/",
        "DNT":                       "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest":            "document",
        "Sec-Fetch-Mode":            "navigate",
        "Sec-Fetch-Site":            "same-origin",
        "Sec-Fetch-User":            "?1",
    }

    for theatre in THEATRES:
        print(f"\n🎭 Checking: {theatre['name']}")
        known = load_state(theatre["state_file"])

        success = False
        for attempt in range(3):
            try:
                print(f"  Attempt {attempt + 1}...")
                resp = scraper.get(theatre["url"], headers=headers, timeout=30)
                print(f"  Status: {resp.status_code}  |  Size: {len(resp.text):,} bytes")

                if resp.status_code == 200:
                    if CHECK_DATE not in resp.url:
                        print(f"  ⚠️  Redirected to {resp.url.split('/')[-1]} — date not open yet")
                        success = True
                        break

                    current = extract_movies_with_timings(resp.text)
                    print(f"  Found {len(current)} movie(s):")
                    for m, t in sorted(current.items()):
                        print(f"    • {m}: {t if t else '(no timings)'}")

                    if known is None:
                        save_state(theatre["state_file"], current)
                        print(f"  📝 First run — baseline saved")
                    else:
                        # New movies not seen before
                        new_movies  = {m: t for m, t in current.items() if m not in known}
                        # New timings for already-known movies
                        new_timings = {
                            m: sorted(set(current[m]) - set(known.get(m, [])))
                            for m in current
                            if m in known and set(current[m]) - set(known.get(m, []))
                        }

                        if new_movies or new_timings:
                            msg = build_alert(theatre["name"], theatre["url"], new_movies, new_timings)
                            print(f"\n{msg}")
                            send_to_all_chats(msg)
                            save_state(theatre["state_file"], current)
                            print(f"  ✨ Alert sent!")
                        else:
                            print(f"  ℹ️  No changes since last check")
                            save_state(theatre["state_file"], current)

                    success = True
                    break

                elif resp.status_code == 403:
                    print(f"  ⚠️  403 Blocked. Waiting 10s...")
                    time.sleep(10)
                else:
                    print(f"  ⚠️  Status {resp.status_code}. Retrying...")
                    time.sleep(5)

            except Exception as e:
                print(f"  ❌ Error: {e}")
                time.sleep(5)

        if not success:
            print(f"  ❌ Failed after 3 attempts: {theatre['name']}")

        time.sleep(3)


if __name__ == "__main__":
    main()
