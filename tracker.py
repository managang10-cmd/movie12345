def main():
    # STEP 1: ALWAYS define known
    known = set()

    try:
        # STEP 2: Load from file if it exists
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                known = set(line.strip() for line in f if line.strip())
            print(f"Loaded {len(known)} known movies.")
        else:
            print("First run: No known_movies.txt found.")

        # STEP 3: Scrape BMS
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        resp = scraper.get(THEATRE_URL, timeout=20)

        if resp.status_code != 200:
            print(f"BMS returned error: {resp.status_code}")
            return

        current = extract_movies(resp.text)
        print(f"Found on page: {current}")

        # STEP 4: Compare safely
        new_items = current - known

        if new_items:
            print(f"NEW MOVIES: {new_items}")

            if known:  # avoids first-run spam
                send_telegram(
                    "🎬 *New Show Added!*\n\n" +
                    "\n".join([f"• {m}" for m in new_items])
                )

        else:
            print("No new shows since last check.")

        # STEP 5: ALWAYS save current state (important fix)
        with open(STATE_FILE, "w") as f:
            f.write("\n".join(sorted(current)))

    except Exception as e:
        print(f"Fatal error: {e}")
