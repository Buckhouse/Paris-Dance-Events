# this scrapes a week's worth of events and puts them into the airtable. 
# to set a specific date, do it like this: python3 week_of_dance_events.py 16/06/2024 
# (where you list the day first, month second, and year last) 

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import openai
import locale

# Set locale to French
locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')

# Airtable setup
AIRTABLE_API_KEY = "patD9W78x0LD98M2V.c7cb3b65d8d72865b5a7f6131ed6365b34c5547a2f1aa3ccbe43094a644d8f79"
BASE_ID = "appMlyQoIVpWTzj79"  # Replace with your base ID
TABLE_NAME = "tblzZL41j94BPih1Q"  # Replace with your table name
API_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

# Set headers
headers = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json"
}

# Set the API key directly
raise Exception("The 'openai.api_key' option isn't read in the client API. You will need to pass it when you instantiate the client, e.g. 'OpenAI(api_key=os.getenv('OPENAI_API_KEY'))'")

class DanceEventsSummarize:
    def __init__(self):
        # Directly use the API key from the environment
        raise Exception("The 'openai.api_key' option isn't read in the client API. You will need to pass it when you instantiate the client, e.g. 'OpenAI(api_key=os.getenv('OPENAI_API_KEY'))'")
        if not openai.api_key:
            raise ValueError("OpenAI API key not set. Please set the 'OPENAI_API_KEY' environment variable.")


# this is the summarizing AI. It takes the scraped detail page text as input. 
    def get_completion(self, details_txt):
        system_message = {
            "role": "system",
            "content": "You are an earnest, intellectual, curious, and positive arts reporter. Please summarize the text in full sentences. The text might be in french, if so, please translate it first."
        }
        user_message = {
            "role": "user",
            "content": f"Here is the text from the website: {details_txt}"
        }
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",  # Ensure you have access to this model
                messages=[system_message, user_message],
                max_tokens=500,
                temperature=0.5
            )
            # this was the key line to edit... adding dot notation to connect message and content
            # if the other ones break, look for this 
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            return "Error in generating summary."
        
def fetch_event_details(url):
    if not url.startswith('http'):
        url = "https://www.offi.fr" + url
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extract text
    text = soup.get_text()
    
    # Find the event name
    entry_name_tag = soup.find('h1', itemprop="name")
    entry_name = entry_name_tag.text.strip() if entry_name_tag else "No event name found"
    
    # Find the venue name
    venue_name_tag = soup.find('div', class_='page-subtitle').find('a') if soup.find('div', class_='page-subtitle') else None
    venue_name = venue_name_tag.text.strip() if venue_name_tag else "No venue name found"
    
    # Find location URL
    location_tag = soup.find("div", {"class": "page-subtitle"}).find("a")
    location_url = location_tag.get("href") if location_tag and location_tag.get("href").startswith('http') else "https://www.offi.fr" + location_tag.get("href")
    
    return text, location_url, entry_name, venue_name

def fetch_venue_website(url):
    if not url.startswith('http'):
        url = "https://www.offi.fr" + url
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    venue_link_tag = None
    links = soup.find_all("a")
    for link in links:
        if link.previous_sibling and "Site web :" in str(link.previous_sibling):
            venue_link_tag = link
            break
        elif link.parent and "Site web :" in str(link.parent.get_text()):
            venue_link_tag = link
            break

    if venue_link_tag:
        venue_url = venue_link_tag.get("href")
    else:
        venue_url = None
    return venue_url

# Function to upload event to Airtable
def upload_to_airtable(data):
    response = requests.post(API_URL, headers=headers, json={"fields": data})
    return response.json()

def get_date_url(date):
    return f"https://www.offi.fr/theatre/operas-ballets-danse.html?criterion_DateDebut={date}&criterion_DateFin={date}"

def main(start_date=None):
    summarizer = DanceEventsSummarize()  # Create an instance of the class

    # Use provided start_date or default to today's date
    if start_date:
        start_date = datetime.strptime(start_date, "%d/%m/%Y")
    else:
        start_date = datetime.today()

    end_date = start_date + timedelta(days=20)

    while start_date <= end_date:
        formatted_date = start_date.strftime("%-d %B %Y")  # Long-form French date format
        date_url = get_date_url(start_date.strftime("%d/%m/%Y"))
        response = requests.get(date_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        entries = soup.find_all("div", {"class": "mini-fiche-details d-flex has-padding-20"})

        for entry in entries:
            img_tag = entry.find("img")
            img_120_url = img_tag["src"]
            img_600_url = img_120_url.replace("/images/120/", "/images/600/")
            details_url = entry.find("a", {"itemprop": "url"})["href"]
            if not details_url.startswith('http'):
                details_url = "https://www.offi.fr" + details_url

            details_txt, location_url, entry_name, venue_name = fetch_event_details(details_url)
            venue_url = fetch_venue_website(location_url)
            summary_txt = summarizer.get_completion(details_txt)

            # Prepare data for Airtable
            event_data = {
                "Event Name": entry_name,
                "Location": venue_name,
                "Date": formatted_date,
                "Venue URL": venue_url,
                "Image URL": img_600_url,
                "Details URL": details_url,
                "Summary": summary_txt
            }

            # Upload to Airtable
            result = upload_to_airtable(event_data)
            print(result)

        start_date += timedelta(days=1)

if __name__ == "__main__":
    import sys
    start_date = sys.argv[1] if len(sys.argv) > 1 else None
    main(start_date)