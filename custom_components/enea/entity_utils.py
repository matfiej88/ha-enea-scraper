"""Common utilities for sensor entities."""
import logging
from .api import EneaApiClient
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_ID
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

def create_api_client_from_config_entry(config_entry):
    """Create an EneaApiClient instance from a config entry."""
    return EneaApiClient(
        config_entry.data[CONF_USERNAME],
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_ID]
    )


async def find_enea_sensor_entities(hass, config_entry):
    """Find all Enea sensor entities for a config entry."""
    entity_registry = er.async_get(hass)
    enea_sensors = []

    for entity in entity_registry.entities.values():
        if (entity.domain == "sensor" and
            entity.unique_id and
            entity.unique_id.startswith(f"enea_{config_entry.entry_id}")):
            enea_sensors.append(entity.entity_id)

    return enea_sensors


def get_entity_component_sensor(hass, entity_id):
    """Get sensor entity component by entity_id."""
    entity_component = hass.data.get("entity_components", {}).get("sensor")
    if entity_component:
        return entity_component.get_entity(entity_id)
    return None
