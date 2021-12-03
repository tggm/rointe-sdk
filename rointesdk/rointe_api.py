"""Rointe API Client"""
from __future__ import annotations

import requests

from typing import Any, Dict, Optional
from collections import namedtuple
from datetime import datetime, timedelta
from rointesdk.device import RointeDevice, ScheduleMode

from rointesdk.settings import (
    AUTH_ACCT_INFO_URL,
    AUTH_HOST,
    AUTH_REFRESH_ENDPOINT,
    AUTH_TIMEOUT_SECONDS,
    AUTH_VERIFY_URL,
    FIREBASE_APP_KEY,
    FIREBASE_DEFAULT_URL,
    FIREBASE_DEVICE_DATA_PATH_BY_ID,
    FIREBASE_DEVICES_PATH_BY_ID,
    FIREBASE_INSTALLATIONS_PATH,
)

ApiResponse = namedtuple("ApiResponse", ["success", "data", "error_message"])


class RointeAPI:
    """Rointe API"""

    def __init__(self, username: str, password: str):
        """Initializes the API"""

        self.username = username
        self.password = password

        self.refresh_token = None
        self.auth_token = None
        self.auth_token_expire_date = None

    def initialize_authentication(self) -> str:
        """
        Initializes the refresh token and cleans
        the original credentials.
        """

        login_data = self._login_user()

        if not login_data.success:
            self.auth_token = None
            self.refresh_token = None
            return login_data.error_message

        self.auth_token = login_data.data["auth_token"]
        self.refresh_token = login_data.data["refresh_token"]
        self.auth_token_expire_date = login_data.data["expires"]

        self._clean_credentials()

        return None

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

        response = requests.post(
            f"{AUTH_REFRESH_ENDPOINT}?key={FIREBASE_APP_KEY}",
            data=payload,
            timeout=AUTH_TIMEOUT_SECONDS,
        )

        if not response:
            return False

        if response.status_code != 200:
            return False

        response_json = response.json()

        if not response_json or "idToken" not in response_json:
            return False

        self.auth_token = response_json["idToken"]
        self.auth_token_expire_date = datetime.now() + timedelta(
            seconds=int(response_json["expiresIn"])
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
        except requests.exceptions.RequestException:
            return ApiResponse(False, None, "cannot_connect")

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

        response = requests.post(
            f"{AUTH_HOST}{AUTH_ACCT_INFO_URL}?key={FIREBASE_APP_KEY}",
            data=payload,
        )

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

        response = requests.get(url, params=args)

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

        response = requests.get(url, params=args)

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

        response = requests.get(
            "{}{}".format(
                FIREBASE_DEFAULT_URL, FIREBASE_DEVICES_PATH_BY_ID.format(device_id)
            ),
            params=args,
        )

        if not response:
            return ApiResponse(False, "No response from API in get_device()")

        if response.status_code != 200:
            return ApiResponse(
                False, None, f"get_device() returned {response.status_code}"
            )

        return ApiResponse(True, response.json(), None)

    def set_device_temp(self, device: RointeDevice, new_temp: float) -> bool:
        """Set the device target temperature."""

        if not self._ensure_valid_auth():
            return ApiResponse(False, None, "Invalid authentication.")

        device_id = device.id
        args = {"auth": self.auth_token}
        body = {"temp": new_temp, "mode": "manual"}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        return self._send_patch_request(device_id, url, args, body)

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
            return self._send_patch_request(device_id, url, args, body)
        elif preset_mode == "eco":
            body = {
                "power": True,
                "mode": "manual",
                "temp": device.eco_temp,
                "status": "eco",
            }
            return self._send_patch_request(device_id, url, args, body)
        elif preset_mode == "Anti-frost":
            body = {
                "power": True,
                "mode": "manual",
                "temp": device.ice_temp,
                "status": "ice",
            }
            return self._send_patch_request(device_id, url, args, body)
        elif preset_mode == "none":
            body = {
                "power": False,
                "mode": "manual",
                "temp": 20,
                "status": "none",
            }
            return self._send_patch_request(device_id, url, args, body)
        else:
            return ApiResponse(False, None, None)

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
            # When turning the device off, we need to set the temperature first.
            set_temp_response = self._send_patch_request(
                device_id, url, args, {"temp": 20}
            )

            if not set_temp_response.success:
                return set_temp_response

            # Then we can turn the device off.
            body = {"power": False, "mode": "manual", "status": "off"}
            return self._send_patch_request(device_id, url, args, body)

        elif hvac_mode == "heat":
            set_temp_response = self._send_patch_request(
                device_id, url, args, {"temp": 20}
            )

            if not set_temp_response.success:
                return set_temp_response

            body = {"mode": "manual", "power": True, "status": "none"}
            return self._send_patch_request(device_id, url, args, body)

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

            set_temp_response = self._send_patch_request(device_id, url, args, body)

            if not set_temp_response.success:
                return set_temp_response

            # and then set AUTO mode.
            request_mode_status = self._send_patch_request(
                device_id, url, args, {"mode": "auto", "power": True}
            )

            return request_mode_status
        else:
            return ApiResponse(False, None, None)

    def _send_patch_request(
        self,
        device_id: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        body=None,
    ) -> ApiResponse:
        """Send a patch request."""

        body["last_sync_datetime_app"] = round(datetime.now().timestamp() * 1000)

        response = requests.patch(
            url,
            params=params,
            json=body,
        )

        if not response:
            return ApiResponse(False, None, None)

        if response.status_code != 200:
            return ApiResponse(False, None, None)

        return ApiResponse(True, None, None)
