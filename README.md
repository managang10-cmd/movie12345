# movie12345


# BOTID TO BE TAKEN FROM TELEGRAM STEPS SEARCH FOR BOTFATHER ONE OLD GUY LOOKS LIKE ROBO PLUS MOBILE PHONE WHICH HE IS HOLDING WILL BE THERE AND AKADA START NOKKI BOT NAME PETTI CREATECHESKOVALA AH HTTP API DETAILS THO SECRET CREATE CHYALA SETTINGS ACTIONS SECRETS POI 

# CHATID EMO USERINFO ANI SEARCH CHESI START CHYALA APUD VACHINA ID THO SAME SECRET CREATE CHYALA CHESI YML AND MAIN PY FILE LA UPDATE CHEYALA

---

## Overview

`movie12345` is an automated movie-theatre tracker for BookMyShow (BMS) shows in specific
theatres across multiple cinema chains. A GitHub Actions workflow (`BMS Tracker 20min`) polls
every 20 minutes, records the currently showing movies per theatre into `known_movies_*.txt`,
and notifies a Telegram group via a bot when new movies appear.

## Theatres Tracked

Each theatre maintains its own known-movies list:

| File | Theatre / Chain |
|------|-----------------|
| `known_movies_imax.txt` | IMAX |
| `known_movies_devi.txt` | Devi |
| `known_movies_art.txt` | Art |
| `known_movies_allu.txt` | Allu |
| `known_movies_saptagiri.txt` | Saptagiri |
| `known_movies_sand_70.txt` | Sathyam (SAND 70mm) |
| `known_movies_sand_35.txt` | Sathyam (SAND 35mm) |
| `known_movies_srisairam.txt` | Sri Sairam |
| `known_movies_sudh_35.txt` | Sudha (35mm) |
| `known_movies.txt` | Aggregate list |

## Files

- `tracker.py` — main scraper/scanner. Runs on schedule, writes the `known_movies_*.txt` files,
  and posts Telegram updates for newly detected movies.
- `clear_txt_files.py` — empties every `known_movies_*.txt` file. Useful to force a fresh
  discovery of shows on the next tracker run.
- `.github/workflows/main.yml` — `BMS Tracker 20min`: scheduled (cron `13,33,53 * * * *`)
  and manually dispatchable tracker.
- `.github/workflows/clear_txt_files.yml` — manual-only action that clears the theatre txt
  files and commits/pushes the emptied files back to `main`.

## Clearing theatre txt files (manual)

From GitHub:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Clear Theatre TXT Files** in the left sidebar.
4. Click **Run workflow** → **Run workflow**.

The workflow empties all `known_movies_*.txt` files, commits the change (message prefixed with
`[skip ci]` to avoid triggering the tracker), and pushes it to `main`.

You can also clear the files locally:

```bash
python clear_txt_files.py
```

## Setup / secrets

The tracker reads Telegram bot tokens and chat IDs (plus a Brevo email API key) from
repository **Secrets**. At minimum provide:

- `BOT_TOKEN` / `CHAT_ID` — primary Telegram bot + destination chat.
- `BOT_TOKEN_2`, `CHAT_ID_2`, … etc. — one pair per theatre/channel the bot reports to.
- `BREVO_API_KEY` and `EMAIL_FROM` — for any email notifications.

> Tip: create the bot via **BotFather** on Telegram, copy the **HTTP API token**, and add it as
> a secret. Get a `CHAT_ID` by messaging `@userinfobot` (or `get_id_bot`) and saving the ID.

## Automation schedule

`BMS Tracker 20min` runs automatically every 20 minutes via cron, so the known-movies lists
and Telegram alerts stay up to date without manual intervention.
