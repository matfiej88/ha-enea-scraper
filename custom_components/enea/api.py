"""API for Enea Scraper."""
import aiohttp
from bs4 import BeautifulSoup
import logging
import json
import csv
import io
import datetime

from .const import TIMEZONE

LOGIN_URL = "https://ebok.enea.pl/logowanie"
CSV_URL = "https://ebok.enea.pl/meter/summaryBalancingChart/csv"

_LOGGER = logging.getLogger(__name__)

class EneaApiClient:
    """Enea API client."""

    def __init__(self, username, password, point_of_delivery_id):
        """Initialize the client."""
        self._username = username
        self._password = password
        self._point_of_delivery_id = point_of_delivery_id
        self._session = aiohttp.ClientSession()
        self._is_logged_in = False

    async def async_download_csv(self, run_date):
        """Downloads and parses CSV data for a specific date.

        Args:
            run_date: Date string in format DD.MM.YYYY

        Returns:
            List of dicts with keys: start, consumed, returned (hourly data)
        """
        if not self._is_logged_in:
            await self.async_login()

        csv_payload = {
            "duration": "day",
            "date": run_date,
            "pointOfDeliveryId": self._point_of_delivery_id
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            csv_data = await self._fetch_csv_data(csv_payload, headers)
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                self._is_logged_in = False
                await self.async_login()
                csv_data = await self._fetch_csv_data(csv_payload, headers)
            else:
                raise

        return self._parse_csv_data(csv_data)

    @staticmethod
    def _to_float(s: str) -> float:
        """Convert string to float, handling special cases.

        Args:
            s: String value to convert

        Returns:
            Float value, or 0.0 if conversion fails or value is empty/dash
        """
        try:
            if s.strip() in ("---", "", "-"):
                return 0.0
            return float(s)
        except ValueError:
            return 0.0

    def _parse_csv_data(self, csv_data: str) -> list:
        """Parse CSV data and return list of hourly consumption/return data.

        Args:
            csv_data: Raw CSV string from Enea API

        Returns:
            List of dicts with keys: start, consumed, returned
        """
        if not csv_data or "Brak danych" in csv_data:
            return []

        csv_data = csv_data.replace('\0', '')
        csv_file = io.StringIO(csv_data)
        csv_reader = csv.reader(csv_file, delimiter=';')

        rows = list(csv_reader)

        if len(rows) <= 1:
            return []

        hourly_data = []

        for row in rows[1:]:
            try:
                if not row or len(row) < 5:
                    continue

                val = row[0].strip()
                val = val.lstrip('=').strip('"').strip("'")
                dt_object = datetime.datetime.strptime(val, '%Y-%m-%d %H:%M')
                dt_object = dt_object.replace(tzinfo=TIMEZONE)
                dt_object = dt_object.replace(minute=0, second=0, microsecond=0)

                consumed_post_str = row[3].replace(',', '.')
                returned_post_str = row[4].replace(',', '.')

                consumed_post = self._to_float(consumed_post_str)
                returned_post = self._to_float(returned_post_str)

                net = consumed_post - returned_post
                consumed = max(net, 0.0)
                returned = max(-net, 0.0)

                if abs(consumed) < 1e-9:
                    consumed = 0.0
                if abs(returned) < 1e-9:
                    returned = 0.0

                hourly_data.append({
                    "start": dt_object,
                    "consumed": consumed,
                    "returned": returned
                })


            except (ValueError, IndexError) as e:
                _LOGGER.debug(f"Error parsing row {row}: {e}")
                continue

        return hourly_data

    async def async_login(self):
        """Logs into ebok.enea.pl."""
        token = await self.async_get_login_token()
        if not token:
            raise Exception('No login token!')

        login_payload = {
            "email": self._username,
            "password": self._password,
            "token": token,
            "btnSubmit": ""
        }

        async with self._session.post(LOGIN_URL, data=login_payload) as resp:
            resp.raise_for_status()
            if 'PHPSESSID' not in self._session.cookie_jar.filter_cookies(LOGIN_URL):
                _LOGGER.error("Login failed: PHPSESSID cookie not found.")
                raise Exception("No PHPSESSID cookie after logging in!")
            self._is_logged_in = True

    async def async_get_login_token(self):
        """Gets the current token from the login form."""
        async with self._session.get(LOGIN_URL) as resp:
            text = await resp.text()
            resp.raise_for_status()
            soup = BeautifulSoup(text, 'html.parser')
            token_input = soup.find('input', {'name': 'token'})
            if not token_input or not token_input.get('value'):
                _LOGGER.error("Login token not found in response HTML.")
                raise Exception('Login token not found!')
            return token_input['value']

    async def _fetch_csv_data(self, csv_payload, headers):
        """Helper method to fetch raw CSV data from the API.

        Returns:
            Raw CSV string from the API response
        """
        async with self._session.post(CSV_URL, data=csv_payload, headers=headers) as resp:
            text = await resp.text()
            resp.raise_for_status()
            try:
                json_data = json.loads(text)
                csv_data = json_data.get("data")
                return csv_data
            except json.JSONDecodeError as e:
                _LOGGER.error(
                    f"Failed to parse JSON response for date {csv_payload.get('date')}. "
                    f"Error: {e}"
                )
                raise

    async def close(self):
        """Close the session."""
        await self._session.close()

