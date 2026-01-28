"""The Enea Scraper integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform, CONF_SCAN_INTERVAL
from datetime import timedelta

from .coordinator import EneaDataUpdateCoordinator
from .entity_utils import create_api_client_from_config_entry

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enea from a config entry."""
    eneaApiClient = create_api_client_from_config_entry(entry)

    coordinator = EneaDataUpdateCoordinator(
        hass,
        eneaApiClient,
        update_interval=timedelta(days=entry.data.get(CONF_SCAN_INTERVAL, 1)),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault("enea", {})
    hass.data["enea"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Close API client session before unloading
    coordinator = hass.data["enea"].get(entry.entry_id)
    if coordinator and hasattr(coordinator, "api_client"):
        await coordinator.api_client.close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data["enea"].pop(entry.entry_id, None)

    return unload_ok


