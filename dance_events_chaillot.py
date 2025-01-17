#!/usr/bin/env python3
"""
dance_events_chaillot.py

Scrapes dance-related events from Chaillot - Théâtre national de la Danse:
https://theatre-chaillot.fr/fr/programmation

It fetches the events, expands date ranges, summarizes with OpenAI, 
and uploads to Airtable.
"""

import os
import re
import requests
import openai
import locale
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
# For the new OpenAI library usage
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

# Set locale for French dates (if available)
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
    logging.debug("French locale 'fr_FR.UTF-8' set successfully.")
except locale.Error:
    logging.warning("French locale 'fr_FR.UTF-8' may not be installed on your system.")

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

if not (OPENAI_API_KEY and AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME):
    logging.critical("Missing required environment variables. Check .env file.")
    raise ValueError("Missing one or more required environment variables.")

# Initialize OpenAI API globally
openai.api_key = OPENAI_API_KEY

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
        self.client = OpenAI(api_key=api_key)

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
            summary = chat_completion.choices[0].message.content
            print("[DEBUG] Received summary from OpenAI.")
            return summary
        except Exception as e:
            print(f"[ERROR] OpenAI API call failed: {e}")
            return "Error in generating summary."

# Airtable configuration
BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

def upload_to_airtable(record_data: dict):
    """Uploads a single event record to Airtable."""
    event_name = record_data.get("Event Name", "No Name")
    logging.debug(f"Uploading to Airtable: {event_name}")
    try:
        response = requests.post(BASE_URL, headers=AIRTABLE_HEADERS, json={"fields": record_data}, timeout=15)
        if response.status_code in [200, 201]:
            logging.info(f"Successfully uploaded: {event_name}")
        else:
            logging.error(f"Airtable upload failed: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Exception during Airtable upload: {e}")

def parse_date_range(times_list: list):
    """Parses a list of <time> elements and returns a list of date objects."""
    if not times_list:
        return []

    try:
        if len(times_list) == 1:
            return [parser.parse(times_list[0]["datetime"]).date()]
        elif len(times_list) == 2:
            start_date = parser.parse(times_list[0]["datetime"]).date()
            end_date = parser.parse(times_list[1]["datetime"]).date()
            return [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    except Exception as e:
        logging.warning(f"Error parsing date range: {e}")
    return []

def scrape_detail_page(url: str) -> str:
    """Fetches additional details from the event's detail page."""
    logging.debug(f"Fetching details from: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        description = soup.find("div", class_="performances-detail-text") or soup.find("main")
        return description.get_text(strip=True, separator="\n") if description else ""
    except Exception as e:
        logging.error(f"Error fetching detail page {url}: {e}")
        return ""

def main():
    summarizer = DanceEventsSummarize()
    base_url = "https://theatre-chaillot.fr"
    listing_url = f"{base_url}/fr/programmation"

    logging.info(f"Fetching listing page: {listing_url}")

    with sync_playwright() as p:
        logging.debug("Launching Playwright browser...")
        browser = p.chromium.launch(headless=True)  # Set to False for debugging
        page = browser.new_page()
        page.goto(listing_url, timeout=30000)

        logging.debug("Waiting for event cards to load...")
        try:
            page.wait_for_selector("a.card.posters__item.group.flex.flex-col.h-full.animated-scall", timeout=20000)
            rendered_html = page.content()
        except Exception as e:
            logging.error(f"Timeout or error waiting for event cards: {e}")
            return

        with open("chaillot_rendered_playwright.html", "w", encoding="utf-8") as f:
            f.write(rendered_html)

        soup = BeautifulSoup(rendered_html, "html.parser")
        event_cards = soup.find_all("a", class_=re.compile(r"card.*posters__item.*group.*"))

        if not event_cards:
            logging.warning("No event cards found. Check HTML file for issues.")
            return

        logging.info(f"Found {len(event_cards)} event cards.")

        for idx, card in enumerate(event_cards, start=1):
            logging.debug(f"Processing event card {idx}...")

            href = card.get("href")
            if not href:
                logging.warning("Event card missing href. Skipping...")
                continue
            event_url = href if href.startswith("http") else f"{base_url}{href}"

            h3 = card.find("h3")
            if not h3:
                logging.warning(f"No title found for event card {idx}. Skipping...")
                continue

            show_title = h3.get_text(strip=True)
            logging.debug(f"Found event title: {show_title}")

            date_li = card.find("li", class_="date")
            if not date_li:
                logging.warning(f"No date found for event: {show_title}. Skipping...")
                continue

            time_tags = date_li.find_all("time")
            event_dates = parse_date_range(time_tags)
            if not event_dates:
                logging.warning(f"Unable to parse dates for event: {show_title}. Skipping...")
                continue

            location_li = date_li.find_next_sibling("li")
            location = location_li.get_text(strip=True) if location_li else "Chaillot"

            image_div = card.find("div", class_="posters__item-image")
            image_url = ""
            if image_div:
                img_tag = image_div.find("img")
                if img_tag:
                    # Construct the absolute URL for the image
                    image_src = img_tag.get("data-src") or img_tag.get("src")
                    if image_src:
                        if image_src.startswith("http"):
                            image_url = image_src
                        else:
                            image_url = f"{base_url}{image_src}"

            logging.debug(f"Extracted image URL: {image_url}")

            details_txt = scrape_detail_page(event_url)
            summary = summarizer.get_completion(details_txt) if details_txt else "No summary available."

            for event_date in event_dates:
                date_str = event_date.strftime("%-d %B %Y")  # e.g., "6 janvier 2025"
                record_data = {
                    "Date": date_str,
                    "Event Name": show_title,
                    "Location": location,
                    "Venue URL": base_url,
                    "Image URL": image_url,
                    "Summary": summary,
                    "Details URL": event_url
                }
                upload_to_airtable(record_data)

if __name__ == "__main__":
    main()