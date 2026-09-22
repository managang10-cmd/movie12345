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
        "url": f"https://www.district.in/movies/sudarshan-35mm-4k-laser-dolby-atmos-rtc-x-roads-hyderabad-in-hyderabad-CD1065725?fromdate=2026-09-24",
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
# District.in returns a 403 WAF block page (tiny ~500 byte body) to plain HTTP
# clients, including cloudscraper — that's a bot-protection block, not a
# Cloudflare JS challenge, so cloudscraper can't solve it. And even on success,
# the showtimes are only present after client-side JavaScript renders the page
# (confirmed by the screenshot: date tabs, filters, and time buttons are all
# JS-driven React/Next.js UI) — there is no static HTML/JSON to scrape.
#
# So this version:
#   1. Tries a cheap cloudscraper GET first (occasionally WAFs are inconsistent).
#   2. Falls back to a real headless browser (Playwright/Chromium) that actually
#      loads and renders the page the way your screenshot shows, then reads the
#      showtimes straight out of the rendered text.
#   3. Parses the rendered text generically: it looks for "<CERT> | <Language>"
#      lines (e.g. "A | Telugu") to find movie titles, language header lines
#      (e.g. "Telugu") to find the showtimes section, and HH:MM AM/PM tokens
#      underneath as the actual times — matching the structure visible on the
#      real page.
#   4. Dumps the rendered HTML to disk if nothing is found, for debugging.
#
# REQUIREMENT: `pip install playwright` and then `playwright install --with-deps
# chromium` must be run once (in CI: add this as a workflow step) before this
# will work. If Playwright/its browser isn't installed, this prints a clear
# error instead of crashing obscurely.

TIME_RE = re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM)\b', re.IGNORECASE)
CERT_LANG_RE = re.compile(r'^[A-Za-z0-9\+]{1,4}\s*\|\s*([A-Za-z]+)\s*$')
KNOWN_LANGUAGES = {
    "telugu", "hindi", "english", "tamil", "kannada", "malayalam",
    "bengali", "marathi", "punjabi", "gujarati", "odia"
}


def parse_district_text(full_text):
    """Parse the fully-rendered page's inner text into {movie: {language: [times]}}.

    Heuristic based on the visible page structure:
        The Paradise
        A | Telugu
        Action, Adventure, Drama
        Telugu
        07:00 AM
        10:45 AM
        ...
    The line just before a "<CERT> | <Language>" line is treated as the movie
    title. A standalone line matching a known language name starts a showtimes
    block; HH:MM AM/PM tokens after it (until the next language header or the
    next movie's cert line) are collected as that language's times.
    """
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    movies = {}
    current_movie = None
    current_lang = None

    for i, line in enumerate(lines):
        cert_m = CERT_LANG_RE.match(line)
        if cert_m:
            title = lines[i - 1] if i - 1 >= 0 else "Unknown Movie"
            current_movie = title
            movies.setdefault(current_movie, {})
            current_lang = None
            continue

        if line.lower() in KNOWN_LANGUAGES:
            current_lang = line
            if current_movie:
                movies[current_movie].setdefault(current_lang, [])
            continue

        if current_movie and current_lang:
            for m in TIME_RE.findall(line):
                t = m.upper()
                if t not in movies[current_movie][current_lang]:
                    movies[current_movie][current_lang].append(t)

    # drop movies/languages with no times collected
    cleaned = {}
    for movie, langs in movies.items():
        kept = {lang: times for lang, times in langs.items() if times}
        if kept:
            cleaned[movie] = kept
    return cleaned


def _fetch_district_rendered_text(url, timeout_ms=45000):
    """Load the page in a real headless browser and return (html, inner_text)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed. Run:\n"
            "    pip install playwright\n"
            "    playwright install --with-deps chromium\n"
            "then re-run this script."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
            locale="en-US",
        )
        page = context.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            # Wait for at least one time-looking string to show up in the DOM.
            try:
                page.wait_for_selector("text=/\\d{1,2}:\\d{2}\\s*(AM|PM)/i", timeout=20000)
            except Exception:
                # Might just be sold out / no shows — still grab whatever rendered.
                page.wait_for_timeout(3000)
            page.wait_for_timeout(1500)  # let any trailing XHR-driven UI settle
            html = page.content()
            text = page.inner_text("body")
        finally:
            browser.close()
        return html, text


def extract_district_showtimes(url, scraper, debug_name="district"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.district.in/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }

    # --- Attempt 1: cheap cloudscraper GET (works if the WAF doesn't trigger) ---
    html = None
    try:
        response = scraper.get(url, headers=headers, timeout=20)
        print(f"  [district] cloudscraper status: {response.status_code}  |  size: {len(response.text):,} bytes")
        if response.status_code == 200 and len(response.text) > 5000:
            html = response.text
        else:
            print(f"  [district] cloudscraper attempt looks blocked (status/size too small) — falling back to headless browser.")
    except Exception as e:
        print(f"  [district] cloudscraper attempt errored: {e} — falling back to headless browser.")

    if html:
        result = parse_district_text(BeautifulSoup(html, "html.parser").get_text("\n"))
        if result:
            return result
        # even a 200 might be a pre-render shell with no JS-populated content

    # --- Attempt 2: real headless browser render ---
    try:
        html, text = _fetch_district_rendered_text(url)
        print(f"  [district] Playwright render size: {len(html):,} bytes")
        result = parse_district_text(text)
        print(f"  [district] Parsed {sum(len(t) for langs in result.values() for t in langs.values())} showtime(s) across {len(result)} movie(s).")
        if result:
            return result
    except Exception as e:
        print(f"  [district] ❌ Headless browser attempt failed: {e}")
        html = html or ""

    # Nothing worked — dump for inspection.
    if DEBUG_DUMP_HTML and html:
        dump_path = f"debug_{debug_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  [district] ⚠️ No showtimes parsed. Rendered HTML dumped to {dump_path} for inspection.")
        except Exception as e:
            print(f"  [district] Could not write debug dump: {e}")

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
