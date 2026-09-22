import os
import re
import json
import requests
import cloudscraper
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ── CONFIGURATION ────────────────────────
CHECK_DATE = "20260924"
DEBUG_DUMP_HTML = True  # dump raw HTML to disk when district scrape returns nothing, for troubleshooting

# Define TELEGRAM_CONFIGS
TELEGRAM_CONFIGS = [
    {"bot_token": os.getenv("BOT_TOKEN"), "chat_id": os.getenv("CHAT_ID")},
    {"bot_token": os.getenv("BOT_TOKEN_2"), "chat_id": os.getenv("CHAT_ID_2")},
    {"bot_token": os.getenv("BOT_TOKEN_3"), "chat_id": os.getenv("CHAT_ID_3")},
    {"bot_token": os.getenv("BOT_TOKEN_NAGESH"), "chat_id": os.getenv("CHAT_ID_NAGESH")},
    {"bot_token": os.getenv("BOT_TOKEN_JERRY"), "chat_id": os.getenv("CHAT_ID_JERRY")},
    {"bot_token": os.getenv("BOT_TOKEN_SATHPREM"), "chat_id": os.getenv("CHAT_ID_SATHPREM")},
    {"bot_token": os.getenv("BOT_TOKEN_SAMOSA"), "chat_id": os.getenv("CHAT_ID_SAMOSA")},
    {"bot_token": os.getenv("BOT_TOKEN_SANKA"), "chat_id": os.getenv("CHAT_ID_SANKA")},
]

THEATRES = [
    {
        "name": "Allu Cinemas - Kokapet",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}",
        "state_file": "known_movies_allu.txt",
        "is_district": False
    },
    {
        "name": "Prasads Imax",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/prasads-multiplex-hyderabad/buytickets/PRHN/{CHECK_DATE}",
        "state_file": "known_movies_imax.txt",
        "is_district": False
    },
    {
        "name": "ART Cinemas",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/art-cinemas-vanasthalipuram/buytickets/ACEV/{CHECK_DATE}",
        "state_file": "known_movies_art.txt",
        "is_district": False
    },
    {
        "name": "sandhya-35",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/sandhya-35mm-2k-dolby-atmos-rtc-x-roads/buytickets/SNDY/{CHECK_DATE}",
        "state_file": "known_movies_sand_35.txt",
        "is_district": False
    },
    {
        "name": "sandhya-70",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/sandhya-70mm-4k-dolby-atmos-rtc-x-roads/buytickets/SMMR/{CHECK_DATE}",
        "state_file": "known_movies_sand_70.txt",
        "is_district": False
    },
    {
        "name": "saptagiri",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/saptagiri-70mm-4k-dolby-digital-rtc-x-roads/buytickets/SART/{CHECK_DATE}",
        "state_file": "known_movies_saptagiri.txt",
        "is_district": False
    },
    {
        "name": "devi",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/devi-70mm-4k-laser-dolby-atmos-rtc-x-roads/buytickets/DVRR/{CHECK_DATE}",
        "state_file": "known_movies_devi.txt",
        "is_district": False
    },
    {
        "name": "sudarshan-35",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/sudarshan-35mm-4k-laser-dolby-atmos-rtc-x-roads/buytickets/SUDA/{CHECK_DATE}",
        "state_file": "known_movies_sudh_35.txt",
        "is_district": False
    },
    {
        "name": "sri sai ram",
        "url": f"https://in.bookmyshow.com/cinemas/hyderabad/sri-sai-ram-70mm-a-c-4k-laser-dolby-71malkajgiri/buytickets/SSRM/{CHECK_DATE}",
        "state_file": "known_movies_srisairam.txt",
        "is_district": False
    },
    {
        "name": "District.in - Sudarshan",
        "url": "https://www.district.in/movies/sudarshan-35mm-4k-laser-dolby-atmos-rtc-x-roads-hyderabad-in-hyderabad-CD1065725",
        "state_file": "known_movies_district.txt",
        "is_district": True
    }
]


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
        print(f"❌ Telegram Error: {e}")
        return False


def send_to_all_chats(msg):
    valid = [c for c in TELEGRAM_CONFIGS if c["bot_token"] and c["chat_id"]]
    if not valid:
        print("⚠️ No Telegram credentials configured.")
    else:
        with ThreadPoolExecutor(max_workers=len(valid)) as executor:
            results = list(executor.map(lambda c: send_telegram(msg, c["bot_token"], c["chat_id"]), valid))
        print(f"✨ Sent to {sum(results)}/{len(results)} Telegram destinations")


def showdatetime_to_time(raw):
    try:
        return datetime.strptime(raw[-4:], "%H%M").strftime("%I:%M %p").lstrip("0")
    except Exception:
        return raw


def extract_movies_with_timings(html):
    soup = BeautifulSoup(html, "html.parser")
    raw = ""
    for script in soup.find_all("script"):
        t = script.string or ""
        if '"EventTitle"' in t and '"ShowTimes"' in t:
            raw = t
            break
    if not raw:
        return {}
    title_matches = list(re.finditer(r'"EventTitle"\s*:\s*"([^"]+)"', raw))
    if not title_matches:
        return {}
    result = {}
    for i, title_match in enumerate(title_matches):
        title = title_match.group(1).strip()
        start = title_match.start()
        end = title_matches[i + 1].start() if i + 1 < len(title_matches) else len(raw)
        movie_block = raw[start:end]
        result[title] = {}
        child_matches = list(re.finditer(r'"EventName"\s*:\s*"([^"]+)"', movie_block))
        for j, child_match in enumerate(child_matches):
            event_name = child_match.group(1).strip()
            lang = event_name.split(" - ")[-1] if " - " in event_name else event_name
            dim_m = re.search(r'"EventDimension"\s*:\s*"([^"]+)"', movie_block[child_match.start():child_match.start() + 300])
            dim = dim_m.group(1) if dim_m else ""
            key = f"{lang} {dim}".strip()
            c_start = child_match.start()
            c_end = child_matches[j + 1].start() if j + 1 < len(child_matches) else len(movie_block)
            child_block = movie_block[c_start:c_end]
            times = []
            for show_m in re.finditer(r'"ShowDateTime"\s*:\s*"(\d{12})"', child_block):
                time_str = showdatetime_to_time(show_m.group(1))
                attr_m = re.search(r'"Attributes"\s*:\s*"([^"]*)"', child_block[show_m.start():show_m.start() + 200])
                attr = attr_m.group(1).strip() if attr_m else ""
                display = f"{time_str} [{attr}]" if attr else time_str
                if display not in times:
                    times.append(display)
            if times:
                result[title][key] = times
        if not result[title]:
            result[title] = {}
    return result


# ── DISTRICT.IN SCRAPER ──────────────────
# District.in is a Next.js app: real showtime data is almost always embedded as
# JSON inside a <script id="__NEXT_DATA__"> tag (or a similar __NUXT__/window.__data
# style blob), not present as plain text in the server-rendered HTML. Scraping
# visible <div> text with regex (the old approach) will usually find nothing even
# when the request itself succeeds. This version:
#   1. Fetches with cloudscraper (same as BMS) instead of plain requests, since
#      District.in also sits behind bot protection.
#   2. Tries to locate and parse embedded JSON and pull out anything that looks
#      like a showtime.
#   3. Falls back to the old div/regex scrape if no JSON is found.
#   4. Prints rich debug info (status code, page size, whether JSON was found)
#      and optionally dumps the raw HTML to disk, so failures are diagnosable
#      instead of silently returning {}.

TIME_RE = re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM)\b', re.IGNORECASE)


def _find_times_in_json(obj, found):
    """Recursively walk a parsed JSON structure and collect anything that looks
    like a show time, from either dict values or list-of-strings."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_l = str(k).lower()
            if isinstance(v, str):
                if TIME_RE.search(v):
                    for m in TIME_RE.findall(v):
                        found.add(m.upper())
                elif any(word in key_l for word in ("time", "slot", "show")) and v:
                    # sometimes times are stored as raw strings like "14:30" or "1430"
                    m2 = re.match(r'^(\d{1,2}):?(\d{2})$', v.strip())
                    if m2:
                        try:
                            t = datetime.strptime(f"{m2.group(1)}:{m2.group(2)}", "%H:%M").strftime("%I:%M %p").lstrip("0")
                            found.add(t)
                        except Exception:
                            pass
            else:
                _find_times_in_json(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _find_times_in_json(item, found)


def extract_district_showtimes(url, scraper, debug_name="district"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.district.in/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        response = scraper.get(url, headers=headers, timeout=30)
        print(f"  [district] Status: {response.status_code}  |  Size: {len(response.text):,} bytes")

        if response.status_code != 200:
            print(f"  [district] ⚠️ Non-200 response, cannot proceed this attempt.")
            return {}

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # --- Strategy 1: __NEXT_DATA__ or any application/json script blob ---
        json_scripts = soup.find_all("script", attrs={"type": "application/json"})
        json_scripts += [s for s in soup.find_all("script", id="__NEXT_DATA__") if s not in json_scripts]

        all_times = set()
        parsed_any_json = False
        for script in json_scripts:
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            try:
                data = json.loads(raw)
                parsed_any_json = True
                _find_times_in_json(data, all_times)
            except json.JSONDecodeError:
                continue

        print(f"  [district] JSON scripts found: {len(json_scripts)}  |  parsed ok: {parsed_any_json}  |  times found in JSON: {len(all_times)}")

        if all_times:
            return {"The Paradise": {"Telugu 2D": sorted(all_times)}}

        # --- Strategy 2: also check for any <script> (not just type=json) that
        # contains inline JS assignments like window.__INITIAL_STATE__ = {...} ---
        for script in soup.find_all("script"):
            t = script.string or script.get_text() or ""
            if not t or ("show" not in t.lower() and "slot" not in t.lower()):
                continue
            m = re.search(r'=\s*(\{.*\})\s*;?\s*$', t.strip(), re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    _find_times_in_json(data, all_times)
                except Exception:
                    pass

        if all_times:
            print(f"  [district] Found {len(all_times)} times via inline JS state blob.")
            return {"The Paradise": {"Telugu 2D": sorted(all_times)}}

        # --- Strategy 3 (fallback): old-style div text scrape ---
        time_divs = soup.find_all('div', class_=re.compile(r'time', re.IGNORECASE))
        showtimes = []
        for div in time_divs:
            time_text = div.get_text(strip=True)
            for m in TIME_RE.findall(time_text):
                if m.upper() not in showtimes:
                    showtimes.append(m.upper())

        print(f"  [district] Fallback div-scrape found: {len(showtimes)} showtimes")

        if showtimes:
            return {"The Paradise": {"Telugu 2D": sorted(showtimes)}}

        # Nothing worked — dump HTML for manual inspection so the JSON/HTML
        # structure can be inspected and the scraper updated.
        if DEBUG_DUMP_HTML:
            dump_path = f"debug_{debug_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            try:
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  [district] ⚠️ No showtimes found by any strategy. Raw HTML dumped to {dump_path} for inspection.")
            except Exception as e:
                print(f"  [district] Could not write debug dump: {e}")

        return {}

    except Exception as e:
        print(f"  [district] ❌ Error accessing District.in URL: {e}")
        return {}


def load_state(path):
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
    with open(path, "w", encoding="utf-8") as f:
        for name, langs in sorted(movies.items()):
            parts = ";".join(f"{lang}:{','.join(times)}" for lang, times in sorted(langs.items()))
            f.write(f"{name}|{parts}\n")


def build_alert(theatre_name, theatre_url, new_movies, new_shows):
    all_movies = list(new_movies.keys()) + list(new_shows.keys())
    first_movie = all_movies[0].upper() if all_movies else "NEW SHOW"
    try:
        formatted_date = datetime.strptime(CHECK_DATE, "%Y%m%d").strftime("%d %b %Y")
    except ValueError:
        formatted_date = CHECK_DATE
    msg = f"*[{first_movie}] - NEW SHOW ALERT!*\n"
    msg += f"Theatre: {theatre_name}\n"
    msg += f"Date: {formatted_date}\n"
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


def main():
    print("--- BMS / DISTRICT SHOW TRACKER ---")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://in.bookmyshow.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }

    for theatre in THEATRES:
        print(f"\nChecking: {theatre['name']}")
        known = load_state(theatre["state_file"])

        success = False
        for attempt in range(3):
            try:
                if theatre.get('is_district', False):
                    current = extract_district_showtimes(theatre["url"], scraper, debug_name=theatre["state_file"].replace(".txt", ""))
                    if not current:
                        print(f"  ⚠️ District scrape returned nothing. Retrying...")
                        time.sleep(5)
                        continue
                else:
                    resp = scraper.get(theatre["url"], headers=headers, timeout=30)
                    print(f"  Status: {resp.status_code}  |  Size: {len(resp.text):,} bytes")
                    if resp.status_code == 200:
                        current = extract_movies_with_timings(resp.text)
                    else:
                        print(f"  ⚠️ Status {resp.status_code}. Retrying...")
                        time.sleep(5)
                        continue

                print(f"  Found {len(current)} movie(s):")
                for movie, langs in sorted(current.items()):
                    print(f"    🎬 {movie}")
                    for lang, times in sorted(langs.items()):
                        print(f"         [{lang}] → {' | '.join(times) if times else '(no times)'}")

                if known is None:
                    save_state(theatre["state_file"], current)
                    print(f"  📝 First run — baseline saved ({len(current)} movies)")
                else:
                    new_movies = {m: langs for m, langs in current.items() if m not in known}
                    new_shows = {}
                    for movie, langs in current.items():
                        if movie not in known:
                            continue
                        added_langs = {}
                        for lang, times in langs.items():
                            known_times = set(known[movie].get(lang, []))
                            added = [t for t in times if t not in known_times]
                            if added:
                                added_langs[lang] = added
                        if added_langs:
                            new_shows[movie] = added_langs

                    if new_movies or new_shows:
                        msg = build_alert(theatre["name"], theatre["url"], new_movies, new_shows)
                        print(f"\n{msg}")
                        send_to_all_chats(msg)
                        save_state(theatre["state_file"], current)
                        print(f"  ✨ Alert sent!")
                    else:
                        print(f"  ℹ️ No changes since last check")
                        save_state(theatre["state_file"], current)

                success = True
                break

            except Exception as e:
                print(f"  ❌ Error: {e}")
                time.sleep(5)

        if not success:
            print(f"  ❌ Failed after 3 attempts: {theatre['name']}")

        time.sleep(3)


if __name__ == "__main__":
    main()
