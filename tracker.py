import os, requests, cloudscraper

# Target URL
CHECK_DATE  = "20260401"
THEATRE_URL = f"https://in.bookmyshow.com/cinemas/hyderabad/allu-cinemas-kokapet/buytickets/ALUC/{CHECK_DATE}"

def diagnostic_test():
    print("--- STARTING CONNECTION TEST ---")
    
    # Try using Cloudscraper (to bypass Cloudflare)
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    
    try:
        print(f"Attempting to access: {THEATRE_URL}")
        resp = scraper.get(THEATRE_URL, timeout=30)
        
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ SUCCESS: BookMyShow is accessible!")
            # Check if we actually got real content or a 'Request Blocked' page
            if "EventTitle" in resp.text or "movieName" in resp.text:
                print("✅ DATA CHECK: Movie data found in HTML!")
            else:
                print("⚠️ DATA CHECK: Page loaded, but no movie markers found (could be a blank schedule).")
        
        elif resp.status_code == 403:
            print("❌ BLOCKED: Cloudflare (403) blocked the GitHub Runner.")
        else:
            print(f"❓ UNKNOWN: Received status {resp.status_code}")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")

    print("--- TEST FINISHED ---")

if __name__ == "__main__":
    diagnostic_test()
