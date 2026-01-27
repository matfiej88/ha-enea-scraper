"""Data update coordinator for Enea integration."""
import logging
import datetime
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import TIMEZONE
from .utils import EneaDataFetcher

_LOGGER = logging.getLogger(__name__)

class EneaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Enea data from API."""

    def __init__(self, hass: HomeAssistant, api_client, update_interval: timedelta):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Enea Sensor",
            update_interval=update_interval,
        )
        self.api_client = api_client
        self.data_fetcher = EneaDataFetcher(api_client)

    async def _async_update_data(self):
        """Fetch data from API only for missing dates."""
        # Get start date from which to fetch (based on last statistic, max 7 days back)
        start_date = await self._get_data_fetch_start_date()

        if start_date is None:
            _LOGGER.info("No data to fetch, statistics are up to date")
            return {}

        today = datetime.date.today()
        end_date = today - datetime.timedelta(days=1)  # yesterday

        _LOGGER.info(f"Fetching data from {start_date} to {end_date}")

        daily_data = await self.data_fetcher.fetch_for_date_range(start_date, end_date)

        return daily_data  # Return dict with date -> list of readings

    async def _get_data_fetch_start_date(self) -> datetime.date | None:
        """Get the start date from which to fetch data based on last available statistic.

        Returns:
            datetime.date from which to start fetching (day after last statistic, max 7 days back)
            None if statistics are up to date (nothing to fetch)
        """
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import get_last_statistics

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        max_start_date = today - datetime.timedelta(days=7)

        # Check both sensors to ensure we don't miss data for either
        statistic_ids = ["sensor.enea_energy_consumed", "sensor.enea_energy_returned"]

        earliest_start_date = None

        try:
            for statistic_id in statistic_ids:
                last_stats = await get_instance(self.hass).async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
                )

                if last_stats and statistic_id in last_stats and last_stats[statistic_id]:
                    last_stat = last_stats[statistic_id][0]
                    last_timestamp = last_stat.get("start")

                    if last_timestamp:
                        if isinstance(last_timestamp, (int, float)):
                            last_datetime = datetime.datetime.fromtimestamp(last_timestamp, tz=TIMEZONE)
                        else:
                            last_datetime = last_timestamp

                        last_date = last_datetime.date()
                        start_date = last_date + datetime.timedelta(days=1)

                        if start_date < max_start_date:
                            start_date = max_start_date

                        # Track the earliest start date needed across both sensors
                        if earliest_start_date is None or start_date < earliest_start_date:
                            earliest_start_date = start_date
                else:
                    # If sensor has no statistics, fetch from max_start_date
                    earliest_start_date = max_start_date

            if earliest_start_date is None:
                earliest_start_date = max_start_date

            if earliest_start_date > yesterday:
                return None

            return earliest_start_date

        except Exception as e:
            _LOGGER.warning(f"Error checking last statistics: {e}, will fetch all 7 days")
            return max_start_date
