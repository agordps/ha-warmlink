"""EXPERIMENTAL number platform: weather compensation curve (slope and offset)."""
import logging
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

# (protocol code, name, min, max, step, unit, icon)
CURVE_NUMBERS = [
    ("compensate_slope", "Weather Comp Slope", 0.1, 2.0, 0.1, None, "mdi:chart-line"),
    ("compensate_offset", "Weather Comp Offset", 15.0, 60.0, 1.0, "\u00b0C", "mdi:chart-line"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the experimental curve numbers (only on units that report H36)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.value("H36") is None:
        return
    async_add_entities(
        WarmlinkCurveNumber(coordinator, entry, *spec) for spec in CURVE_NUMBERS
    )


class WarmlinkCurveNumber(CoordinatorEntity, NumberEntity):
    """Writable weather-compensation curve parameter."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, code, name, vmin, vmax, step, unit, icon):
        """Initialize the number."""
        super().__init__(coordinator)
        self._entry = entry
        self._code = code
        self._attr_unique_id = f"{entry.entry_id}_{code}_number"
        self._attr_name = name
        self._attr_native_min_value = vmin
        self._attr_native_max_value = vmax
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to the same device as the other entities."""
        name, model = "WarmLink", "Heat Pump"
        info = self.coordinator.device_info or {}
        if (info.get("device_nick_name") or "").strip():
            name = info["device_nick_name"]
        elif (info.get("cust_model") or "").strip():
            name = info["cust_model"]
        if (info.get("cust_model") or "").strip():
            model = info["cust_model"]
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=name,
            manufacturer="WarmLink",
            model=model,
        )

    @property
    def available(self) -> bool:
        """Available while the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def native_value(self):
        """Current value as reported by the device."""
        for item in self.coordinator.data or []:
            if item.get("code") == self._code:
                try:
                    return float(item.get("value"))
                except (TypeError, ValueError):
                    return None
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the device."""
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set %s", self._code)
            return
        out = f"{value:.1f}" if self._attr_native_step < 1 else str(int(round(value)))
        LOGGER.warning("WarmLink: (experimental) requesting %s=%s", self._code, out)
        resp = await self.coordinator.api.set_value(device_code, self._code, out)
        LOGGER.warning("WarmLink: (experimental) %s=%s response: %s", self._code, out, resp)
        await self.coordinator.async_request_refresh()
