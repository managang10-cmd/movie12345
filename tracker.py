import os, re, requests, cloudscraper, time
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
        results = list(ex.map(
            lambda c: send_telegram(msg, c["bot_token"], c["chat_id"]), valid
        ))
    print(f"✨ Sent to {sum(results)}/{len(results)} destinations")


# ── Extraction ────────────────────────────
def showdatetime_to_time(raw):
    """'202604031245' → '12:45 PM'"""
    try:
        return datetime.strptime(raw[-4:], "%H%M").strftime("%I:%M %p").lstrip("0")
    except Exception:
        return raw


def extract_movies_with_timings(html):
    """
    Correctly maps each movie to its own show timings using
    character-position slicing between consecutive EventTitle occurrences.

    BMS structure in script:
      EventTitle → ChildEvents[] → ShowTimes[] → ShowDateTime (202604031245)

    Returns:
      {
        "Movie Name": {
          "Hindi 2D": ["8:00 AM", "12:10 PM [PCX HDR by BARCO]"],
          "Telugu 2D": ["6:20 PM"]
        }
      }
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find the script block that has both EventTitle and ShowTimes
    raw = ""
    for script in soup.find_all("script"):
        t = script.string or ""
        if '"EventTitle"' in t and '"ShowTimes"' in t:
            raw = t
            break

    if not raw:
        return {}

    # Find positions of all EventTitle occurrences
    title_matches = list(re.finditer(r'"EventTitle"\s*:\s*"([^"]+)"', raw))
    if not title_matches:
        return {}

    result = {}

    for i, title_match in enumerate(title_matches):
        title = title_match.group(1).strip()

        # Slice from this EventTitle to the next (or end)
        start = title_match.start()
        end   = title_matches[i + 1].start() if i + 1 < len(title_matches) else len(raw)
        movie_block = raw[start:end]

        result[title] = {}

        # Find each ChildEvent block (one per language/format)
        child_matches = list(re.finditer(r'"EventName"\s*:\s*"([^"]+)"', movie_block))

        for j, child_match in enumerate(child_matches):
            event_name = child_match.group(1).strip()

            # Language = last part after " - "
            lang = event_name.split(" - ")[-1] if " - " in event_name else event_name

            # Dimension (2D/3D/4DX)
            dim_m = re.search(r'"EventDimension"\s*:\s*"([^"]+)"',
                              movie_block[child_match.start():child_match.start() + 300])
            dim = dim_m.group(1) if dim_m else ""
            key = f"{lang} {dim}".strip()

            # Slice this child block up to the next child
            c_start = child_match.start()
            c_end   = child_matches[j + 1].start() if j + 1 < len(child_matches) else len(movie_block)
            child_block = movie_block[c_start:c_end]

            # Extract all ShowDateTime + Attributes pairs
            times = []
            for show_m in re.finditer(r'"ShowDateTime"\s*:\s*"(\d{12})"', child_block):
                time_str = showdatetime_to_time(show_m.group(1))
                # Grab Attributes in the next 200 chars
                attr_m = re.search(r'"Attributes"\s*:\s*"([^"]*)"',
                                   child_block[show_m.start():show_m.start() + 200])
                attr = attr_m.group(1).strip() if attr_m else ""
                display = f"{time_str} [{attr}]" if attr else time_str
                if display not in times:
                    times.append(display)

            if times:
                result[title][key] = times

        # Keep movie even if no child breakdown found
        if not result[title]:
            result[title] = {}

    return result


# ── State helpers ─────────────────────────
# State format per line:  MovieName|Lang Dim:T1,T2;Lang Dim:T3
# Example: Dhurandhar The Revenge|Hindi 2D:8:00 AM,12:10 PM;Telugu 2D:6:20 PM

def load_state(path):
    """Returns { movie: { lang: [times] } } or None on first run."""
    if not os.path.exists(path):
        return None
    data = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                name, rest = line.split("|", 1)
                data[name] = {}
                if rest:
                    for part in rest.split(";"):
                        if ":" in part:
                            lang, times_str = part.split(":", 1)
                            data[name][lang] = [t for t in times_str.split(",") if t]
            else:
                data[line] = {}
    return data


def save_state(path, movies):
    """Save { movie: { lang: [times] } } to file."""
    with open(path, "w", encoding="utf-8") as f:
        for name, langs in sorted(movies.items()):
            parts = ";".join(
                f"{lang}:{','.join(times)}"
                for lang, times in sorted(langs.items())
            )
            f.write(f"{name}|{parts}\n")


# ── Alert builder ─────────────────────────
def build_alert(theatre_name, theatre_url, new_movies, new_shows):
    """
    new_movies: { movie: { lang: [times] } }  — brand new movies
    new_shows:  { movie: { lang: [new_times] } } — new slots for existing movies
    """
    ts  = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    msg = f"🎬 *NEW SHOW ALERT!*\n"
    msg += f"🏢 *Theatre:* {theatre_name}\n"
    msg += f"📅 *At:* {ts}\n"
    msg += f"🔗 [Book Now]({theatre_url})\n"

    if new_movies:
        msg += "\n*🆕 New Movies Added:*\n"
        for movie, langs in sorted(new_movies.items()):
            msg += f"\n🎥 *{movie}*\n"
            if langs:
                for lang, times in sorted(langs.items()):
                    msg += f"  `{lang}` → {' | '.join(times)}\n"
            else:
                msg += "  _(open BMS to see timings)_\n"

    if new_shows:
        msg += "\n*🕐 New Show Times Added:*\n"
        for movie, langs in sorted(new_shows.items()):
            msg += f"\n🎥 *{movie}*\n"
            for lang, times in sorted(langs.items()):
                msg += f"  `{lang}` → {' | '.join(times)}\n"

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
                        print(f"  ⚠️  Redirected → date not open yet on BMS")
                        success = True
                        break

                    current = extract_movies_with_timings(resp.text)

                    # Print what was found
                    print(f"  Found {len(current)} movie(s):")
                    for movie, langs in sorted(current.items()):
                        print(f"    🎬 {movie}")
                        for lang, times in sorted(langs.items()):
                            print(f"         [{lang}] → {' | '.join(times) if times else '(no times)'}")

                    if known is None:
                        # First run — save baseline, no alert
                        save_state(theatre["state_file"], current)
                        print(f"  📝 First run — baseline saved ({len(current)} movies)")

                    else:
                        # Detect brand new movies
                        new_movies = {
                            m: langs for m, langs in current.items()
                            if m not in known
                        }

                        # Detect new show slots for existing movies
                        new_shows = {}
                        for movie, langs in current.items():
                            if movie not in known:
                                continue  # already in new_movies
                            added_langs = {}
                            for lang, times in langs.items():
                                known_times = set(known[movie].get(lang, []))
                                added = [t for t in times if t not in known_times]
                                if added:
                                    added_langs[lang] = added
                            if added_langs:
                                new_shows[movie] = added_langs

                        if new_movies or new_shows:
                            msg = build_alert(
                                theatre["name"], theatre["url"],
                                new_movies, new_shows
                            )
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
