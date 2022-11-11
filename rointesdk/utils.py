"""Utility methods"""
import datetime as dt

DEFAULT_TIME_ZONE: dt.tzinfo = dt.timezone.utc


def now(time_zone=None) -> dt.datetime:
    """Get now in specified time zone."""
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)


def find_max_fw_version(data, device_class: str, version: str) -> str:
    """Finds the latest FW version for a specific device class and version"""

    if device_class in data:
        if version in data[device_class] and "end_user" in data[device_class][version]:
            root = data[device_class][version]["end_user"]

            max_version = None

            for entry in root:
                ptr = version.parse(entry)
                if max_version is None or ptr > max_version:
                    max_version = ptr

            return max_version

    return None
