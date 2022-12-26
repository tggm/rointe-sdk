"""Data objects"""

from __future__ import annotations
from datetime import datetime


class EnergyConsumptionData:
    """Data object for energy statistics."""

    start: datetime
    end: datetime
    kwh: float
    effective_power: float

    created: datetime

    def __init__(
        self,
        start: datetime,
        end: datetime,
        kwh: float,
        effective_power: float,
        created: datetime,
    ):
        """Initialize the value."""
        self.start = start
        self.end = end
        self.kwh = kwh
        self.effective_power = effective_power
        self.created = created
