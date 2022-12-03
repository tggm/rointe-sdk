"""Rointe API Client"""
from __future__ import annotations

import requests
from requests.exceptions import RequestException

from typing import Any, Dict, Optional
from collections import namedtuple
from datetime import datetime, timedelta

from .utils import build_update_map
from .device import RointeDevice, ScheduleMode
from .dto import EnergyConsumptionData

from .settings import (
    AUTH_ACCT_INFO_URL,
    AUTH_HOST,
    AUTH_REFRESH_ENDPOINT,
    AUTH_TIMEOUT_SECONDS,
    AUTH_VERIFY_URL,
    ENERGY_STATS_MAX_TRIES,
    FIREBASE_APP_KEY,
    FIREBASE_DEFAULT_URL,
    FIREBASE_DEVICE_DATA_PATH_BY_ID,
    FIREBASE_DEVICE_ENERGY_PATH_BY_ID,
    FIREBASE_DEVICES_PATH_BY_ID,
    FIREBASE_GLOBAL_SETTINGS_PATH,
    FIREBASE_INSTALLATIONS_PATH,
)

ApiResponse = namedtuple("ApiResponse", ["success", "data", "error_message"])


class RointeAPI:
    """Rointe API Communication. Handles low level calls to the API."""

    def __init__(self, username: str, password: str):
        """Initializes the API"""

        self.username = username
        self.password = password

        self.refresh_token = None
        self.auth_token = None
        self.auth_token_expire_date = None

    def initialize_authentication(self) -> ApiResponse:
        """
        Initializes the refresh token and cleans
        the original credentials.
        """

        login_data: ApiResponse = self._login_user()

        if not login_data.success:
            self.auth_token = None
            self.refresh_token = None
            return login_data

        self.auth_token = login_data.data["auth_token"]
        self.refresh_token = login_data.data["refresh_token"]
        self.auth_token_expire_date = login_data.data["expires"]

        self._clean_credentials()

        return ApiResponse(True, None, None)

    def _clean_credentials(self):
        """Cleans authentication values"""
        self.username = None
        self.password = None

    def is_logged_in(self) -> bool:
        """Check if the login was successful."""
        return self.auth_token is not None and self.refresh_token is not None

    def _ensure_valid_auth(self) -> bool:
        """Ensure there is a valid authentication token present."""

        now = datetime.now()

        if not self.auth_token or (
            self.auth_token_expire_date and self.auth_token_expire_date < now
        ):
            if not self._refresh_token():
                return False

        return True

    def _refresh_token(self) -> bool:
        """Refreshes authentication."""

        payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}

        try:
            response = requests.post(
                f"{AUTH_REFRESH_ENDPOINT}?key={FIREBASE_APP_KEY}",
                data=payload,
                timeout=AUTH_TIMEOUT_SECONDS,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return False

        if response.status_code != 200:
            return False

        response_json = response.json()

        if not response_json or "id_token" not in response_json:
            return False

        self.auth_token = response_json["id_token"]
        self.auth_token_expire_date = datetime.now() + timedelta(
            seconds=int(response_json["expires_in"])
        )
        self.refresh_token = response_json["refresh_token"]

        return True

    def _login_user(self) -> ApiResponse:
        """Log the user in."""

        payload = {
            "email": self.username,
            "password": self.password,
            "returnSecureToken": True,
        }

        try:
            response = requests.post(
                f"{AUTH_HOST}{AUTH_VERIFY_URL}?key={FIREBASE_APP_KEY}",
                data=payload,
                timeout=AUTH_TIMEOUT_SECONDS,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if response.status_code == 400:
            return ApiResponse(
                False,
                None,
                "invalid_auth",
            )

        if response.status_code != 200:
            return ApiResponse(
                False,
                None,
                "response_invalid",
            )

        response_json = response.json()

        if not response_json or "idToken" not in response_json:
            return ApiResponse(False, None, "invalid_auth_response")

        data = {
            "auth_token": response_json["idToken"],
            "expires": datetime.now()
            + timedelta(seconds=int(response_json["expiresIn"])),
            "refresh_token": response_json["refreshToken"],
        }

        return ApiResponse(True, data, None)

    def get_local_id(self) -> ApiResponse:
        """Retrieve user local_id value."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        payload = {"idToken": self.auth_token}

        try:
            response = requests.post(
                f"{AUTH_HOST}{AUTH_ACCT_INFO_URL}?key={FIREBASE_APP_KEY}",
                data=payload,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(
                False, None, "No response from API call to get_local_id()"
            )

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_local_id() returned {response.status_code}"
            )

        response_json = response.json()

        return ApiResponse(True, response_json["users"][0]["localId"], None)

    def get_installation_by_id(
        self, installation_id: str, local_id: str
    ) -> ApiResponse:
        """Retrieve a specific installation by ID."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        args = {
            "auth": self.auth_token,
            "orderBy": '"userid"',
            "equalTo": f'"{local_id}"',
        }

        url = f"{FIREBASE_DEFAULT_URL}{FIREBASE_INSTALLATIONS_PATH}"

        try:
            response = requests.get(url, params=args)
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(
                False, "No response from API in get_installation_by_id()"
            )

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_installation_by_id() returned {response.status_code}"
            )

        reponse_json = response.json()

        if len(reponse_json) == 0 or installation_id not in reponse_json:
            return ApiResponse(False, None, "No Rointe installation found.")

        return ApiResponse(True, reponse_json[installation_id], None)

    def get_latest_firmware(self) -> ApiResponse:
        """Retrieves the latest firmware available for each device type"""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        url = f"{FIREBASE_DEFAULT_URL}{FIREBASE_GLOBAL_SETTINGS_PATH}"
        args = {"auth": self.auth_token}

        try:
            response = requests.get(
                url,
                params=args,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(False, "No response from API in get_latest_firmware()")

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_latest_firmware() returned {response.status_code}"
            )

        data = response.json()

        if len(data) == 0:
            return ApiResponse(False, None, "Global Settings is empty.")

        return ApiResponse(True, build_update_map(data), None)

    def get_installations(self, local_id: str) -> ApiResponse:
        """Retrieve the client's installations."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        args = {
            "auth": self.auth_token,
            "orderBy": '"userid"',
            "equalTo": f'"{local_id}"',
        }
        url = f"{FIREBASE_DEFAULT_URL}{FIREBASE_INSTALLATIONS_PATH}"

        try:
            response = requests.get(url, params=args)
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(False, "No response from API in get_installations()")

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_installations() returned {response.status_code}"
            )

        reponse_json = response.json()

        if len(reponse_json) == 0:
            return ApiResponse(False, None, "No Rointe installations found.")

        installations = {}

        for key in reponse_json.keys():
            installations[key] = reponse_json[key]["location"]

        return ApiResponse(True, installations, None)

    def get_device(self, device_id: str) -> ApiResponse:
        """Retrieve device data."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        args = {"auth": self.auth_token}

        try:
            response = requests.get(
                "{}{}".format(
                    FIREBASE_DEFAULT_URL, FIREBASE_DEVICES_PATH_BY_ID.format(device_id)
                ),
                params=args,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(False, "No response from API in get_device()")

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_device() returned {response.status_code}"
            )

        return ApiResponse(True, response.json(), None)

    def get_latest_energy_stats(self, device_id: str) -> ApiResponse:
        """Retrieve the latest energy consumption values."""

        result: EnergyConsumptionData
        now = datetime.now()

        # Attempt to retrieve the latest value. If not found, go back one hour. Max 5 tries.
        attempts = ENERGY_STATS_MAX_TRIES
        target_date = now.replace(
            minute=0, second=0, microsecond=0
        )  # Strip minutes, seconds and microseconds.

        while attempts > 0:
            result: ApiResponse = self._retrieve_hour_energy_stats(
                device_id, target_date
            )

            if result.error_message == "No energy stats found.":
                # Try again.
                attempts = attempts - 1
                target_date = target_date - timedelta(hours=1)
            else:
                # It's either a success or an error message, return the ApiResponse.
                return result

        return ApiResponse(False, None, "Max tries exceeded.")

    def _retrieve_hour_energy_stats(
        self, device_id: str, target_date: datetime
    ) -> ApiResponse:
        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        # Sample URL /history_statistics/device_id/daily/2022/01/21/energy/010000.json
        args = {"auth": self.auth_token}
        url = "{}{}{}/energy/{}0000.json".format(
            FIREBASE_DEFAULT_URL,
            FIREBASE_DEVICE_ENERGY_PATH_BY_ID.format(device_id),
            target_date.strftime("%Y/%m/%d"),
            target_date.strftime("%H"),
        )

        try:
            response = requests.get(url, params=args)
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(
                False, "No response from API in _retrieve_hour_energy_stats()"
            )

        if response.status_code != 200:
            return ApiResponse(
                False,
                None,
                f"_retrieve_hour_energy_stats() returned {response.status_code}",
            )

        response_json = response.json()

        if not response_json or len(response_json) == 0:
            return ApiResponse(False, None, "No energy stats found.")

        data = EnergyConsumptionData(
            created=datetime.now,
            start=target_date,
            end=target_date + timedelta(hours=1),
            kwh=float(response_json["kw_h"]),
            effective_power=float(response_json["effective_power"]),
        )

        return ApiResponse(True, data, None)

    def set_device_temp(self, device: RointeDevice, new_temp: float) -> ApiResponse:
        """Set the device target temperature."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        device_id = device.id
        args = {"auth": self.auth_token}
        body = {"temp": new_temp, "mode": "manual", "power": True}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        return self._send_patch_request(url, args, body)

    def set_device_preset(self, device: RointeDevice, preset_mode: str) -> ApiResponse:
        """Set the preset."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        device_id = device.id
        args = {"auth": self.auth_token}
        body: Dict[str, Any] = {}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        if preset_mode == "comfort":
            body = {
                "power": True,
                "mode": "manual",
                "temp": device.comfort_temp,
                "status": "comfort",
            }

        elif preset_mode == "eco":
            body = {
                "power": True,
                "mode": "manual",
                "temp": device.eco_temp,
                "status": "eco",
            }
        elif preset_mode == "Anti-frost":
            body = {
                "power": True,
                "mode": "manual",
                "temp": device.ice_temp,
                "status": "ice",
            }

        return self._send_patch_request(url, args, body)

    def set_device_mode(self, device: RointeDevice, hvac_mode: str) -> ApiResponse:
        """Set the HVAC mode."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        device_id = device.id
        args = {"auth": self.auth_token}
        body: Dict[str, Any] = {}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        if hvac_mode == "off":
            # This depends if the device is in Auto or Manual modes.
            if device.mode == "auto":
                body = {"power": False, "mode": "auto", "status": "off"}
                return self._send_patch_request(url, args, body)
            else:
                # When turning the device off, we need to set the temperature first.
                set_mode_response = self._send_patch_request(url, args, {"temp": 20})

                if not set_mode_response.success:
                    return set_mode_response

                # Then we can turn the device off.
                body = {"power": False, "mode": "manual", "status": "off"}
                return self._send_patch_request(url, args, body)

        elif hvac_mode == "heat":
            set_mode_response = self._send_patch_request(
                url, args, {"temp": device.comfort_temp}
            )

            if not set_mode_response.success:
                return set_mode_response

            body = {"mode": "manual", "power": True, "status": "none"}
            return self._send_patch_request(url, args, body)

        elif hvac_mode == "auto":
            current_mode: ScheduleMode = device.get_current_schedule_mode()

            # When changing modes we need to send the proper
            # temperature also.
            if current_mode == ScheduleMode.COMFORT:
                body = {"temp": device.comfort_temp}
            elif current_mode == ScheduleMode.ECO:
                body = {"temp": device.eco_temp}
            elif device.ice_mode:
                body = {"temp": device.ice_temp}
            else:
                body = {"temp": 20}

            set_mode_response = self._send_patch_request(url, args, body)

            if not set_mode_response.success:
                return set_mode_response

            # and then set AUTO mode.
            request_mode_status = self._send_patch_request(
                url, args, {"mode": "auto", "power": True}
            )

            return request_mode_status
        else:
            return ApiResponse(False, None, f"Invalid HVAC Mode {hvac_mode}.")

    def _send_patch_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        body=None,
    ) -> ApiResponse:
        """Send a patch request."""

        body["last_sync_datetime_app"] = round(datetime.now().timestamp() * 1000)

        try:
            response = requests.patch(
                url,
                params=params,
                json=body,
            )
        except RequestException as e:
            return ApiResponse(False, None, f"Network error {e}")

        if not response:
            return ApiResponse(False, None, None)

        if response.status_code != 200:
            return ApiResponse(False, None, None)

        return ApiResponse(True, None, None)
