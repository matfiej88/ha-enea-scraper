"""API for Enea Scraper."""
import aiohttp
from bs4 import BeautifulSoup
import logging
import json
import datetime

from .const import TIMEZONE

LOGIN_URL = "https://ebok.enea.pl/logowanie"
METER_CHART_URL = "https://ebok.enea.pl/meter/summaryBalancingChart"
JSON_URL = "https://ebok.enea.pl/meter/summaryBalancingChart"

# Default timeout for all HTTP requests (in seconds)
DEFAULT_TIMEOUT = 30

_LOGGER = logging.getLogger(__name__)

class EneaApiClient:
    """Enea API client."""

    def __init__(self, username, password, point_of_delivery_id=None, timeout=DEFAULT_TIMEOUT):
        """Initialize the client."""
        self._username = username
        self._password = password
        self._point_of_delivery_id = point_of_delivery_id
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = None
        self._is_logged_in = False

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False

    def _ensure_session(self):
        """Ensure session is created."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def async_download_csv(self, run_date):
        """Downloads and parses JSON data for a specific date.

        Args:
            run_date: Date string in format DD.MM.YYYY

        Returns:
            List of dicts with keys: start, consumed, returned (hourly data)
        """
        import asyncio

        self._ensure_session()

        if not self._is_logged_in:
            await self.async_login()

        # Auto-fetch point_of_delivery_id if not set
        if not self._point_of_delivery_id:
            await self.async_fetch_point_of_delivery_id()

        payload = {
            "duration": "day",
            "date": run_date,
            "pointOfDeliveryId": self._point_of_delivery_id
        }
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,pl;q=0.8,de;q=0.7",
            "Connection": "keep-alive",
            "Origin": "https://ebok.enea.pl",
            "Referer": "https://ebok.enea.pl/meter/summaryBalancingChart",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }


        try:
            json_data = await self._fetch_json_data(payload, headers)
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout fetching JSON data for {run_date}")
            raise
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                self._is_logged_in = False
                await self.async_login()
                try:
                    json_data = await self._fetch_json_data(payload, headers)
                except asyncio.TimeoutError:
                    _LOGGER.error(f"Timeout fetching JSON data for {run_date} (retry after re-login)")
                    raise
            else:
                raise

        return self._parse_json_data(json_data)

    def _parse_json_data(self, json_data: list) -> list:
        """Parse JSON data and return list of hourly consumption/return data.

        Args:
            json_data: List of hourly records from Enea API

        Returns:
            List of dicts with keys: start, consumed, returned
        """
        if not json_data:
            return []

        hourly_data = []

        for record in json_data:
            try:
                # Parse dateFrom field (e.g., "2023-07-13T00:00:00")
                date_from_str = record.get("dateFrom")
                if not date_from_str:
                    continue

                dt_object = datetime.datetime.fromisoformat(date_from_str)
                dt_object = dt_object.replace(tzinfo=TIMEZONE)
                dt_object = dt_object.replace(minute=0, second=0, microsecond=0)

                # Get consumed and returned values (after balancing)
                # Handle None values by converting to 0.0
                consumed_raw = record.get("aecasb")
                returned_raw = record.get("eaecasb")

                consumed = float(consumed_raw) if consumed_raw is not None else 0.0
                returned = float(returned_raw) if returned_raw is not None else 0.0

                # Handle small floating point values
                if abs(consumed) < 1e-9:
                    consumed = 0.0
                if abs(returned) < 1e-9:
                    returned = 0.0

                hourly_data.append({
                    "start": dt_object,
                    "consumed": consumed,
                    "returned": returned
                })

            except (ValueError, KeyError, TypeError):
                continue

        return hourly_data

    async def async_login(self):
        """Logs into ebok.enea.pl."""
        self._ensure_session()

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

    async def async_fetch_point_of_delivery_id(self):
        """Fetch point_of_delivery_id from the meter chart page.

        Returns:
            str: The point of delivery ID
        """
        self._ensure_session()

        if not self._is_logged_in:
            await self.async_login()

        async with self._session.get(METER_CHART_URL) as resp:
            text = await resp.text()
            resp.raise_for_status()
            soup = BeautifulSoup(text, 'html.parser')

            # Find checkbox with data-point-of-delivery-id attribute
            checkbox = soup.find('input', {'data-point-of-delivery-id': True})

            if not checkbox:
                _LOGGER.error("Could not find point-of-delivery-id in meter chart page")
                raise Exception('Point of delivery ID not found!')

            pod_id = checkbox.get('data-point-of-delivery-id')
            if not pod_id:
                raise Exception('Point of delivery ID is empty!')

            _LOGGER.info(f"Found point of delivery ID: {pod_id}")
            self._point_of_delivery_id = pod_id
            return pod_id

    async def async_get_login_token(self):
        """Gets the current token from the login form."""
        self._ensure_session()

        async with self._session.get(LOGIN_URL) as resp:
            text = await resp.text()
            resp.raise_for_status()
            soup = BeautifulSoup(text, 'html.parser')
            token_input = soup.find('input', {'name': 'token'})
            if not token_input or not token_input.get('value'):
                _LOGGER.error("Login token not found in response HTML.")
                raise Exception('Login token not found!')
            return token_input['value']

    async def _fetch_json_data(self, payload, headers):
        """Helper method to fetch JSON data from the API.

        Returns:
            List of hourly records from the API response
        """
        async with self._session.post(JSON_URL, data=payload, headers=headers) as resp:
            resp.raise_for_status()

            response_text = await resp.text()

            try:
                json_data = json.loads(response_text)
                return json_data
            except (json.JSONDecodeError, ValueError) as e:
                _LOGGER.error(
                    f"Failed to parse JSON response for date {payload.get('date')}. "
                    f"Error: {e}"
                )
                raise

    async def close(self):
        """Close the session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            self._is_logged_in = False

