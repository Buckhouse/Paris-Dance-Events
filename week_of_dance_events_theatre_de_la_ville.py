#!/usr/bin/env python3

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import locale

# For loading .env
from dotenv import load_dotenv

# For the new openai library usage
from openai import OpenAI

# -------------------------------------------------------------------
# 1) LOAD ENV + LOCALE
# -------------------------------------------------------------------
load_dotenv()  # This loads any OPENAI_API_KEY from your .env file
locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")

# -------------------------------------------------------------------
# 2) AIRTABLE CONFIG
# -------------------------------------------------------------------
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "YOUR_AIRTABLE_KEY")

BASE_ID = "appMlyQoIVpWTzj79"
TABLE_NAME = "tblzZL41j94BPih1Q"
API_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

# -------------------------------------------------------------------
# 3) SUMMARIZER CLASS
# -------------------------------------------------------------------
class DanceEventsSummarize:
    def __init__(self):
        # Make sure openai.api_key is set from env or .env
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not set. Please set the 'OPENAI_API_KEY' "
                "environment variable or define it in your .env file."
            )

        # Create the new OpenAI client
        self.client = OpenAI(
            api_key=api_key  # This is the default, but we can pass it explicitly
        )

    # *** MAKE SURE THIS METHOD IS INDENTED UNDER THE CLASS ***
    def get_completion(self, details_txt: str) -> str:
        system_message = {
            "role": "system",
            "content": (
                "You are an earnest, intellectual, curious, and positive arts reporter. "
                "Please summarize the text in full sentences. If the text is in French, "
                "please translate it first."
            ),
        }
        user_message = {
            "role": "user",
            "content": f"Here is the text from the website: {details_txt}",
        }

        try:
            print("[DEBUG] Sending text to OpenAI for summarization...")
            chat_completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[system_message, user_message],
                max_tokens=500,
                temperature=0.5,
            )

            # Access .content instead of ["content"]
            summary = chat_completion.choices[0].message.content
            print("[DEBUG] Received summary from OpenAI.")
            return summary
        except Exception as e:
            print(f"[ERROR] OpenAI API call failed: {e}")
            return "Error in generating summary."

# -------------------------------------------------------------------
# 4) HELPER: FETCH EVENT DETAILS
# -------------------------------------------------------------------
def fetch_event_details(url: str):
    """
    Fetch the detail page and parse out name, text, venue, etc.
    """
    print(f"[DEBUG] Fetching details from event URL: {url}")
    resp = requests.get(url)
    if not resp.ok:
        print(f"[ERROR] Failed to fetch event URL: {resp.status_code}")
        return None, None, None, None

    soup = BeautifulSoup(resp.content, "html.parser")

    # Extract text from the entire page
    text = soup.get_text(separator="\n", strip=True)

    # Attempt to find <span class="place"> for the venue
    place_tag = soup.find("span", {"class": "place"})
    venue_name = place_tag.get_text(strip=True) if place_tag else "Théâtre de la Ville"

    # Attempt to find <h1 class="page-title"> for the event name
    event_name_tag = soup.find("h1", class_="page-title")
    event_name = event_name_tag.get_text(strip=True) if event_name_tag else "No event name found"

    # Hardcode the main venue site
    venue_url = "https://www.theatredelaville-paris.com/"

    print(f"[DEBUG] Event name: {event_name}")
    print(f"[DEBUG] Details text length: {len(text)} characters")
    return text, venue_url, event_name, venue_name


# -------------------------------------------------------------------
# 5) HELPER: UPLOAD TO AIRTABLE
# -------------------------------------------------------------------
def upload_to_airtable(data: dict):
    """
    Upload a single event record to Airtable.
    """
    print(f"[DEBUG] Uploading to Airtable: {data.get('Event Name', 'No event name')}")
    try:
        response = requests.post(API_URL, headers=AIRTABLE_HEADERS, json={"fields": data})
        print(f"[DEBUG] Airtable response status: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to upload to Airtable: {e}")
        return {"error": str(e)}


# -------------------------------------------------------------------
# 6) HELPER: PARSE EVENT DATE
# -------------------------------------------------------------------
def parse_event_date(raw_date_str: str):
    """
    Attempt to parse a date string like '06 18 janv. 2025' or '10 18 janv. 2025'.
    If parse fails, return None.
    """
    try:
        parts = raw_date_str.strip().split()
        # Example: ["06", "18", "janv.", "2025"]
        if len(parts) < 3:
            print(f"[WARNING] Not enough parts to parse date: '{raw_date_str}'")
            return None

        year_str = parts[-1]
        month_fr = parts[-2].replace(".", "").lower()
        fr_month_map = {
            "janv": "01",
            "févr": "02",
            "mars": "03",
            "avr": "04",
            "mai": "05",
            "juin": "06",
            "juil": "07",
            "août": "08",
            "sept": "09",
            "oct": "10",
            "nov": "11",
            "déc": "12",
        }
        month_num = fr_month_map.get(month_fr, "01")

        day_str = parts[0]
        date_str = f"{day_str}/{month_num}/{year_str}"

        event_date = datetime.strptime(date_str, "%d/%m/%Y")
        return event_date
    except ValueError:
        print(f"[WARNING] Couldn't parse date string: '{raw_date_str}'")
        return None


# -------------------------------------------------------------------
# 7) MAIN SCRAPER
# -------------------------------------------------------------------
def main(start_date_str=None):
    summarizer = DanceEventsSummarize()

    # Decide start date
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%d/%m/%Y")
    else:
        start_date = datetime.today()
    end_date = start_date + timedelta(days=60)

    print(f"[DEBUG] Scraping Théâtre de la Ville from {start_date} to {end_date}")

    base_url = "https://www.theatredelaville-paris.com/fr/spectacles/saison-24-25/danse"
    print(f"[DEBUG] Requesting base URL: {base_url}")

    resp = requests.get(base_url)
    if not resp.ok:
        print(f"[ERROR] Failed to get base URL: {resp.status_code}")
        return

    soup = BeautifulSoup(resp.content, "html.parser")
    events = soup.find_all("article", class_="event-item layout-horizontal page-block")
    print(f"[DEBUG] Found {len(events)} events on the page.")

    # Loop over found events
    for evt in events:
        link_tag = evt.find("a", href=True)
        if not link_tag:
            print("[WARNING] No link found in this article block. Skipping...")
            continue

        event_url = link_tag["href"]
        if not event_url.startswith("http"):
            event_url = "https://www.theatredelaville-paris.com" + event_url

        date_tag = evt.find("p", class_="event-item-date")
        raw_date_str = date_tag.get_text(strip=True) if date_tag else ""
        print(f"[DEBUG] Raw date string: '{raw_date_str}'")

        event_date = parse_event_date(raw_date_str)

        # Next, fetch the details page
        details_txt, venue_url, entry_name, venue_name = fetch_event_details(event_url)
        if not details_txt:
            continue

        # Summarize with the new style
        summary_txt = summarizer.get_completion(details_txt)

        # If parse succeeded, put a nice date, else fallback
        if event_date:
            date_for_airtable = event_date.strftime("%-d %B %Y")  # e.g. "18 janvier 2025"
        else:
            date_for_airtable = raw_date_str

        event_data = {
            "Event Name": entry_name,
            "Location": venue_name,
            "Date": date_for_airtable,
            "Venue URL": venue_url,
            "Details URL": event_url,
            "Summary": summary_txt,
        }

        print(f"[DEBUG] Preparing to upload event: {entry_name}")
        result = upload_to_airtable(event_data)
        print(f"[DEBUG] Airtable upload result: {result}")

    print("[DEBUG] Finished processing all events.")


# -------------------------------------------------------------------
# 8) ENTRY POINT
# -------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    # If user passed e.g. 16/01/2025 on the CLI
    start_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(start_arg)