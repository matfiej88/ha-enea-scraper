#!/usr/bin/env python3
"""
Script to fetch historical energy data from ENEA e-BOK API.
Fetches daily consumption/return data from 2019-12-20 to present and saves to JSONL.
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
from typing import List, Set
from dotenv import load_dotenv

# Load configuration from config.env
load_dotenv('custom_components/enea/data/config.env')

# API configuration
API_URL = "https://ebok.enea.pl/meter/summaryBalancingChart"
PHPSESSID = os.getenv('PHPSESSID', '')
POINT_OF_DELIVERY_ID = os.getenv('POINT_OF_DELIVERY_ID', 'ce1a50df-b907-e911-80de-005056b326a5')

# Session cookie

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8,de;q=0.7",
    "Connection": "keep-alive",
    "Origin": "https://ebok.enea.pl",
    "Referer": "https://ebok.enea.pl/meter/summaryBalancingChart",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Cookie": f"PHPSESSID={PHPSESSID}; k1238573940294996039=!pssshTLDR82wuhakMimdbUUHRvykILtQOklxxBRjfoZeT2TI650zWVEN+9hgqTdjMNcwbfLuYSGhng=="
}

OUTPUT_FILE = "enea_historical_data.jsonl"
START_DATE = datetime(2019, 12, 20)
DELAY_SECONDS = 0.1  # 100ms delay between requests

# Create a session to maintain cookies

def generate_date_range(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Generate list of dates from start_date to end_date (inclusive)."""
    dates = []
    current_date = start_date

    while current_date <= end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)

    return dates


def format_date_for_api(date: datetime) -> str:
    """Format date as DD.MM.YYYY for API request."""
    return date.strftime("%d.%m.%Y")


def load_existing_dates(filename: str) -> Set[str]:
    """Load already fetched dates from existing JSONL file."""
    if not os.path.exists(filename):
        return set()

    existing_dates = set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get('date'):
                        existing_dates.add(record['date'])
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Warning: Error reading existing file: {e}")

    return existing_dates


def fetch_day_data(date_str: str) -> dict:
    """Fetch energy data for a specific day."""
    payload = {
        "duration": "day",
        "date": date_str,
        "pointOfDeliveryId": POINT_OF_DELIVERY_ID
    }

    try:
        response = requests.post(
            API_URL,
            data=payload,
            headers=HEADERS,
            timeout=30,
            allow_redirects=False  # Don't follow redirects (301/302 means auth failed)
        )
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        return {
            "date": date_str,
            "requested_at": datetime.now().isoformat(),
            "status": "success",
            "data": data
        }

    except requests.exceptions.HTTPError as e:
        return {
            "date": date_str,
            "requested_at": datetime.now().isoformat(),
            "status": "error",
            "error": f"HTTP {e.response.status_code}: {str(e)}"
        }
    except json.JSONDecodeError as e:
        return {
            "date": date_str,
            "requested_at": datetime.now().isoformat(),
            "status": "error",
            "error": f"JSON decode error: {str(e)}"
        }
    except Exception as e:
        return {
            "date": date_str,
            "requested_at": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }


def append_to_jsonl(filename: str, record: dict):
    """Append a record to JSONL file."""
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def main():
    """Main function to fetch all data and write to JSONL."""
    print("Starting ENEA data fetch...")
    print(f"API URL: {API_URL}")
    print(f"Point of Delivery ID: {POINT_OF_DELIVERY_ID}")
    print(f"PHPSESSID: {PHPSESSID[:10]}...{PHPSESSID[-5:] if len(PHPSESSID) > 15 else ''}")
    print(f"Output file: {OUTPUT_FILE}")
    print("-" * 70)

    # Generate date range from start date to yesterday
    end_date = datetime.now() - timedelta(days=1)
    dates = generate_date_range(START_DATE, end_date)
    print(f"Date range: {format_date_for_api(START_DATE)} to {format_date_for_api(end_date)}")
    print(f"Total days to fetch: {len(dates)}")

    # Load existing dates to skip
    existing_dates = load_existing_dates(OUTPUT_FILE)
    if existing_dates:
        print(f"Found {len(existing_dates)} already fetched dates in {OUTPUT_FILE}")

    # Filter out already fetched dates
    dates_to_fetch = [d for d in dates if format_date_for_api(d) not in existing_dates]
    print(f"Days to fetch (after skipping existing): {len(dates_to_fetch)}")
    print("-" * 70)

    if not dates_to_fetch:
        print("✓ All dates already fetched!")
        return

    # Counters
    success_count = 0
    error_count = 0

    # Fetch data for each day
    for idx, date in enumerate(dates_to_fetch, 1):
        date_str = format_date_for_api(date)
        print(f"[{idx}/{len(dates_to_fetch)}] Fetching {date_str}...", end=" ", flush=True)

        result = fetch_day_data(date_str)

        # Append to JSONL file
        append_to_jsonl(OUTPUT_FILE, result)

        if result['status'] == 'success':
            data_points = len(result.get('data', []))
            print(f"✓ Got {data_points} hourly records")
            success_count += 1
        else:
            print(f"✗ Error: {result.get('error', 'Unknown error')}")
            error_count += 1

        # Delay between requests (except for the last one)
        if idx < len(dates_to_fetch):
            time.sleep(DELAY_SECONDS)

    # Summary
    print("-" * 70)
    print(f"✓ Done! Data saved to {OUTPUT_FILE}")
    print(f"Successfully fetched: {success_count} days")
    print(f"Errors: {error_count} days")
    print(f"Total records in file: {len(existing_dates) + success_count}")


if __name__ == "__main__":
    main()
