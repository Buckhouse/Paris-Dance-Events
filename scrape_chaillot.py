import os
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI
import time
# Load environment variables
load_dotenv()

# AirTable Configuration
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "YOUR_AIRTABLE_KEY")
BASE_ID = "appMlyQoIVpWTzj79"
TABLE_NAME = "tblzZL41j94BPih1Q"
API_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

# OpenAI Configuration
class DanceEventsSummarize:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not set. Please set it in your .env file.")
        self.client = OpenAI(api_key=api_key)

    def get_completion(self, details_txt):
        system_message = {
            "role": "system",
            "content": "You are a helpful assistant summarizing dance event details. Translate if necessary."
        }
        user_message = {
            "role": "user",
            "content": details_txt
        }

        try:
            chat_completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[system_message, user_message],
                max_tokens=500,
                temperature=0.5,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"[ERROR] OpenAI API call failed: {e}")
            return "Error generating summary."

# Fetch dynamic content using Selenium
def fetch_dynamic_content(url):
    service = Service("/path/to/chromedriver")  # Update this with your actual path
    driver = webdriver.Chrome(service=service)
    try:
        driver.get(url)
        time.sleep(5)  # Wait for JavaScript to load
        html = driver.page_source
        return BeautifulSoup(html, "html.parser")
    finally:
        driver.quit()

# Parse date range into individual dates
def parse_event_dates(start_date, end_date):
    date_list = []
    start = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S")
    end = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S")
    delta = timedelta(days=1)

    while start <= end:
        date_list.append(start.strftime("%-d %B %Y"))
        start += delta

    return date_list

# Fetch event details
def fetch_event_details(url):
    print(f"[DEBUG] Fetching details from: {url}")
    resp = requests.get(url)
    if not resp.ok:
        print(f"[ERROR] Failed to fetch event URL: {resp.status_code}")
        return None, None, None, None, None

    soup = BeautifulSoup(resp.content, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    venue_name = "Théâtre National de Chaillot"
    event_name = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Unknown Event"
    image_tag = soup.find("picture")
    image_url = image_tag.find("img")["src"] if image_tag and image_tag.find("img") else "No image found"
    return text, url, event_name, venue_name, image_url

# Upload to Airtable
def upload_to_airtable(data):
    try:
        response = requests.post(API_URL, headers=AIRTABLE_HEADERS, json={"fields": data})
        print(f"[DEBUG] Airtable response status: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to upload to Airtable: {e}")
        return {"error": str(e)}

# Main scraping logic
def main():
    summarizer = DanceEventsSummarize()
    base_url = "https://theatre-chaillot.fr/fr/programmation"
    soup = fetch_dynamic_content(base_url)

    events = soup.find_all("a", class_="card posters__item group flex flex-col h-full animated-scall")
    print(f"[DEBUG] Found {len(events)} events on the page.")

    for event in events:
        event_url = "https://theatre-chaillot.fr" + event["href"]
        date_tags = event.find_all("time")

        if len(date_tags) >= 2:
            start_date = date_tags[0]["datetime"]
            end_date = date_tags[1]["datetime"]
        elif len(date_tags) == 1:
            start_date = end_date = date_tags[0]["datetime"]
        else:
            print(f"[WARNING] No dates found for event: {event_url}")
            continue

        event_dates = parse_event_dates(start_date, end_date)
        details_txt, venue_url, entry_name, venue_name, image_url = fetch_event_details(event_url)
        if not details_txt:
            continue

        summary_txt = summarizer.get_completion(details_txt)

        for event_date in event_dates:
            event_data = {
                "Event Name": entry_name,
                "Location": venue_name,
                "Date": event_date,
                "Venue URL": venue_url,
                "Details URL": event_url,
                "Summary": summary_txt,
                "Image URL": image_url,
            }

            print(f"[DEBUG] Uploading event: {entry_name} on {event_date}")
            upload_to_airtable(event_data)

    print("[DEBUG] Finished processing all events.")

if __name__ == "__main__":
    main()