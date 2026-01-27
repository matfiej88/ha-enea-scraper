"""Utility functions for Enea integration."""
import logging
import datetime

_LOGGER = logging.getLogger(__name__)


class EneaDataFetcher:
    """Handles fetching and organizing energy data from Enea API."""

    def __init__(self, api_client):
        """Initialize the data fetcher.

        Args:
            api_client: EneaApiClient instance to use for fetching data
        """
        self.client = api_client

    async def _fetch_for_date(self, date_str: str) -> list:
        """Fetch and parse data for a specific date.

        Args:
            date_str: Date string in format DD.MM.YYYY

        Returns:
            List of parsed hourly data for that date
        """
        import asyncio
        import aiohttp

        try:
            _LOGGER.debug(f"Fetching data for {date_str}...")
            hourly_data = await self.client.async_download_csv(date_str)
            _LOGGER.debug(f"Successfully fetched data for {date_str}")
            return hourly_data if hourly_data else []
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout error fetching data for {date_str} - request took too long")
            return []
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Network error fetching data for {date_str}: {e}")
            return []
        except Exception as e:
            _LOGGER.error(f"Error fetching data for {date_str}: {e}", exc_info=True)
            return []

    async def fetch_for_date_range(self, start_date: datetime.date, end_date: datetime.date) -> dict:
        """Fetch and parse data for a range of dates.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dict where key is date and value is list of hourly readings for that date.
            ALL dates in the range are included - days with no data have empty lists.
        """
        num_days = (end_date - start_date).days + 1
        date_range = [start_date + datetime.timedelta(days=i) for i in range(num_days)]

        daily_data = {}
        for current_date in date_range:
            date_str = current_date.strftime('%d.%m.%Y')
            hourly_readings = await self._fetch_for_date(date_str)
            daily_data[current_date] = hourly_readings if hourly_readings else []


        return daily_data
