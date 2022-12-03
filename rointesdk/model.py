"""Data Model enumerations."""

from __future__ import annotations
from enum import Enum


class RointeProduct(Enum):
    """Device Models and Versions enum"""

    def __init__(self, product_name: str, device_type: str, version: str):
        """Initializes the enum."""
        self.product_name = product_name
        self.device_type = device_type
        self.version = version

    RADIATOR_V1 = "DeltaUltimate Radiator", "radiator", "v1"
    RADIATOR_V2 = "D-Series Radiator", "radiator", "v2"
    TOWEL_RAIL_V1 = "Towel v1", "towel", "v1"
    TOWEL_RAIL_V2 = "Towel Rail", "towel", "v2"
    WATER_HEATER_V1 = "Water Heater v1", "acs", "v1"
    WATER_HEATER_V2 = "Water Heater v2", "acs", "v2"
    THERMO_V2 = "Thermostat", "therm", "v2"


class DeviceMode(Enum):
    """Device working modes."""

    AUTO = "auto"
    MAN = "manual"


class ScheduleMode(Enum):
    """Radiator schedule modes."""

    COMFORT = "C"
    ECO = "E"
    NONE = "O"
