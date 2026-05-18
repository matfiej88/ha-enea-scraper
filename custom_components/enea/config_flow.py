"""Config flow for Enea Scraper."""
import voluptuous as vol
import datetime
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_ID, CONF_SCAN_INTERVAL
import logging

_LOGGER = logging.getLogger(__name__)

class EneaConfigFlow(config_entries.ConfigFlow, domain="enea"):
    """Handle a config flow for Enea Scraper."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Validate credentials and fetch point_of_delivery_id
            try:
                from .api import EneaApiClient
                async with EneaApiClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD]
                ) as client:
                    # This will login and fetch the ID
                    await client.async_login()
                    pod_id = await client.async_fetch_point_of_delivery_id()

                    # Add the fetched ID to user_input
                    user_input[CONF_ID] = pod_id

                return self.async_create_entry(title="Enea Energy Meter", data=user_input)
            except Exception as e:
                _LOGGER.error(f"Failed to validate credentials or fetch ID: {e}")
                errors["base"] = "auth"

        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=1): int,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return EneaOptionsFlowHandler()


class EneaOptionsFlowHandler(config_entries.OptionsFlow):
    """Enea options flow."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "force_update":
                await self._async_force_update()
                return self.async_create_entry(title="", data={})

            elif action == "force_reimport":
                await self._async_force_reimport()
                return self.async_create_entry(title="", data={})

            elif action == "import_historical":
                return await self.async_step_historical_date()

            return self.async_create_entry(title="", data={})

        data_schema = vol.Schema({
            vol.Optional("action"): vol.In({
                "force_update": "Force Update - Refresh data immediately",
                "force_reimport": "Force Full Reimport - Clear all statistics and reimport from scratch",
                "import_historical": "Import Historical Data - Import data from a specific date"
            })
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "title": "Enea Integration Actions"
            }
        )

    async def _async_force_update(self):
        """Force update - trigger coordinator to fetch missing data immediately."""
        try:
            coordinator = self.hass.data["enea"][self.config_entry.entry_id]
            await coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(f"Error during force update: {e}")

    async def async_step_historical_date(self, user_input=None):
        """Handle historical data import date selection."""
        errors = {}

        if user_input is not None:
            start_date_str = user_input.get("start_date")
            if start_date_str:
                try:
                    # Parse date string to datetime.date object
                    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                    await self._async_import_historical_data(start_date)
                    return self.async_create_entry(title="", data={})
                except ValueError:
                    # Invalid date format, show form again with error
                    errors["start_date"] = "Invalid date format. Use YYYY-MM-DD format."

        return self.async_show_form(
            step_id="historical_date",
            data_schema=self._get_historical_date_schema(),
            errors=errors,
            description_placeholders={
                "title": "Historical Data Import",
                "description": "Select the starting date for historical data import. Data will be imported day by day from this date until today. Use YYYY-MM-DD format."
            }
        )

    def _get_historical_date_schema(self):
        """Get the historical date schema."""
        # Default to 30 days ago
        import datetime
        default_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

        return vol.Schema({
            vol.Required("start_date", default=default_date): str,
        })

    async def _async_force_reimport(self):
        """Force full reimport - fetch last 7 days and override existing statistics."""
        import datetime

        try:
            today = datetime.date.today()
            start_date = today - datetime.timedelta(days=7)
            end_date = today - datetime.timedelta(days=1)

            await self._async_refresh_data_for_period(start_date, end_date)
        except Exception as e:
            _LOGGER.error(f"Error during full reimport: {e}")

    async def _async_import_historical_data(self, start_date):
        """Import historical data from the specified start date."""
        import datetime

        try:
            today = datetime.date.today()
            await self._async_refresh_data_for_period(start_date, today)
        except Exception as e:
            _LOGGER.error(f"Error during historical data import: {e}")

    async def _async_refresh_data_for_period(self, start_date, end_date):
        """Fetch data for a date range and push to sensors.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        """
        from .utils import EneaDataFetcher
        from .entity_utils import (
            create_api_client_from_config_entry,
            find_enea_sensor_entities,
            get_entity_component_sensor
        )

        # Create API client and fetch data
        async with create_api_client_from_config_entry(self.config_entry) as client:
            fetcher = EneaDataFetcher(client)

            _LOGGER.info(f"Fetching data from {start_date} to {end_date}")
            daily_data_dict = await fetcher.fetch_for_date_range(start_date, end_date)

        if not daily_data_dict:
            _LOGGER.warning(f"No data fetched for period {start_date} to {end_date}")
            return

        # Get sensors and push data
        enea_sensors = await find_enea_sensor_entities(self.hass, self.config_entry)

        if not enea_sensors:
            _LOGGER.warning("No enea sensors found in entity registry")
            return

        for sensor_entity_id in enea_sensors:
            sensor = get_entity_component_sensor(self.hass, sensor_entity_id)
            if sensor and hasattr(sensor, 'async_import_statistics_direct'):
                await sensor.async_import_statistics_direct(sensor_entity_id, daily_data_dict)
                _LOGGER.info(f"Data import completed for {sensor_entity_id}")
            else:
                _LOGGER.warning(f"Could not find sensor object for {sensor_entity_id}")
