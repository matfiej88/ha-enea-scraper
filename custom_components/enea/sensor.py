"""Platform for sensor integration."""
from __future__ import annotations
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data["enea"][entry.entry_id]

    sensors = [
        EneaConsumptionSensor(coordinator),
        EneaEnergyReturnedSensor(coordinator),
    ]
    async_add_entities(sensors)

class EneaBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Enea sensors."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, data_key: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._attr_name = name
        self._attr_unique_id = f"enea_{coordinator.config_entry.entry_id}_{data_key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self.hass.async_create_task(self.async_import_statistics())

    @property
    def native_value(self):
        """Return None to prevent last reading from affecting current day charts and aggregations."""
        return None

    async def async_import_statistics(self):
        """Import statistics from coordinator data using recorder cumulative sum."""
        if not self.entity_id:
            _LOGGER.warning(f"Entity ID not available yet for {self._attr_name}, skipping statistics import")
            return

        statistic_id = self.entity_id
        daily_data_dict = self.coordinator.data

        if not daily_data_dict:
            return

        await self.async_import_statistics_direct(statistic_id, daily_data_dict)


    async def async_import_statistics_direct(self, statistic_id, daily_data_dict):
        """Import statistics for days with data and placeholder for days without."""
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.models import StatisticData, StatisticMetaData, StatisticMeanType
        from homeassistant.components.recorder.statistics import async_import_statistics
        from datetime import datetime
        from .const import TIMEZONE

        if not daily_data_dict:
            return

        all_readings = []
        for readings in daily_data_dict.values():
            if readings:
                all_readings.extend(readings)

        if all_readings:
            earliest_date = min(reading["start"] for reading in all_readings)
            base_stat = await get_instance(self.hass).async_add_executor_job(
                self._get_last_statistic_before, statistic_id, earliest_date
            )
            base_sum = float(base_stat.get("sum", 0.0)) if base_stat else 0.0
        else:
            base_sum = 0.0

        statistics = []
        current_sum = base_sum

        for date_key in sorted(daily_data_dict.keys()):
            readings = daily_data_dict[date_key]

            if not readings:
                # For days without data, add a single statistic at midnight with state=0
                # This marks the day as processed without affecting the cumulative sum
                day_start = datetime.combine(date_key, datetime.min.time()).replace(tzinfo=TIMEZONE)
                statistics.append(StatisticData(start=day_start, sum=current_sum, state=0.0))
            else:
                for reading in sorted(readings, key=lambda x: x["start"]):
                    value = float(reading.get(self._data_key) or 0.0)
                    current_sum += value
                    statistics.append(StatisticData(start=reading["start"], sum=current_sum, state=value))

        if statistics:
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=self._attr_name,
                source="recorder",
                statistic_id=statistic_id,
                unit_of_measurement=self.native_unit_of_measurement,
                unit_class="energy",
                mean_type=StatisticMeanType.NONE,
            )
            await async_import_statistics(self.hass, metadata, statistics)


    def _get_last_statistic_before(self, statistic_id, before_date):
        """Get the last statistics record before the given date."""
        from homeassistant.components.recorder.statistics import statistics_during_period
        from datetime import timedelta

        start_time = before_date - timedelta(days=2)
        end_time = before_date - timedelta(seconds=1)

        try:
            stats = statistics_during_period(
                self.hass,
                start_time,
                end_time,
                {statistic_id},
                "hour",
                None,
                {"sum"}
            )

            if stats and statistic_id in stats and stats[statistic_id]:
                all_stats = stats[statistic_id]
                last_stat = all_stats[-1]

                return {
                    "start": last_stat.get("start"),
                    "sum": last_stat.get("sum", 0.0)
                }

        except Exception as e:
            _LOGGER.error(f"Error in _get_last_statistic_before: {e}")

        return None


class EneaConsumptionSensor(EneaBaseSensor):
    """Representation of an Enea Consumption Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "consumed", "Enea Energy Consumed")


class EneaEnergyReturnedSensor(EneaBaseSensor):
    """Representation of an Enea Energy Returned Sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "returned", "Enea Energy Returned")
