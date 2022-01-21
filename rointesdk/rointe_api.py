"""Rointe API Client"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
import requests
from collections import namedtuple
from datetime import datetime, time, timedelta
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

_LOGGER = logging.getLogger(__name__)

ApiResponse = namedtuple("ApiResponse", ["success", "data", "error_message"])


class RointeAPI:
    def __init__(self, username: str, password: str):

        self.username = username
        self.password = password

        self.refresh_token = None
        self.auth_token = None
        self.auth_token_expire_date = None

        self._initialize_authentication()

    def _initialize_authentication(self) -> None:
        """Initializes the refresh token and cleans
            the original credentials."""

        login_data = self.login_user(self.username, self.password)

        if not login_data.success:
            _LOGGER.error(
                "Unable to authenticate user: %s",
                login_data.error_message)

            self.auth_token = None
            self.refresh_token = None
            return

        self.auth_token = login_data.data["auth_token"]
        self.refresh_token = login_data.data["refresh_token"]
        self.auth_token_expire_date = login_data.data["expires"]

        self._clean_credentials()

    def _clean_credentials(self):
        """Cleans authentication values"""
        self.username = None
        self.password = None

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
            _LOGGER.error("No response while refreshing authentication")
            return False

        if response.status_code != 200:
            _LOGGER.error(
                "Invalid response [%s] when refreshing authentication",
                response.status_code,
            )
            return False

        response_json = response.json()

        if not response_json or "idToken" not in response_json:
            _LOGGER.error("Error while refreshing authentication")
            return False

        self.auth_token = response_json["idToken"]
        self.auth_token_expire_date = datetime.now() + timedelta(
            seconds=int(response_json["expiresIn"])
        )
        self.refresh_token = response_json["refresh_token"]

        return True

    def login_user(self, username: str, password: str) -> ApiResponse:
        """Log the user in."""

        payload = {"email": username, "password": password, "returnSecureToken": True}

        response = requests.post(
            f"{AUTH_HOST}{AUTH_VERIFY_URL}?key={FIREBASE_APP_KEY}",
            data=payload,
            timeout=AUTH_TIMEOUT_SECONDS,
        )

        if not response:
            return ApiResponse(False, None, "No response while authenticating")

        if response.status_code != 200:
            return ApiResponse(
                False,
                None,
                f"Invalid response code {response.status_code} while authenticating",
            )

        response_json = response.json()

        if not response_json or "idToken" not in response_json:
            return ApiResponse(False, None, "API Error while logging in")

        data = {
            "auth_token": response_json["idToken"],
            "expires": datetime.now()
            + timedelta(seconds=int(response_json["expiresIn"])),
            "refresh_token": response_json["refreshToken"],
        }

        return ApiResponse(True, data, None)

    def get_local_id(self, auth_token: str) -> ApiResponse:
        """Retrieve user local_id value."""

        if not auth_token:
            return ApiResponse(False, None, "Authentication not present")

        payload = {"idToken": auth_token}

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
        self, installation_id: str, local_id: str, auth_token: str
    ) -> ApiResponse:
        """Retrieve a specific installation by ID."""

        args = {"auth": auth_token, "orderBy": '"userid"', "equalTo": f'"{local_id}"'}

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

    def get_installations(self, local_id: str, auth_token: str) -> ApiResponse:
        """Retrieve the client's installations."""

        args = {"auth": auth_token, "orderBy": '"userid"', "equalTo": f'"{local_id}"'}
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

    def get_device(device_id: str, auth_token: str) -> ApiResponse:
        """Retrieve device data."""

        args = {"auth": auth_token}

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

    def set_device_temp(
        self, device: RointeDevice, auth_token: str, new_temp: float
    ) -> bool:
        """Set the device target temperature."""

        device_id = device.id
        args = {"auth": auth_token}
        body = {"temp": new_temp, "mode": "manual"}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        return self._send_patch_request(device_id, url, args, body)

    def set_device_preset(
        self, device: RointeDevice, auth_token: str, preset_mode: str
    ) -> bool:
        """Set the preset."""

        device_id = device.id
        args = {"auth": auth_token}
        body: Dict[str, Any] = {}

        url = "{}{}".format(
            FIREBASE_DEFAULT_URL, FIREBASE_DEVICE_DATA_PATH_BY_ID.format(device_id)
        )

        if preset_mode == "off":
            body = {"power": False, "mode": "manual"}
            return self._send_patch_request(device_id, url, args, body)

        elif preset_mode == "heat":
            body = {"mode": "manual", "power": True, "status": "none"}
            return self._send_patch_request(device_id, url, args, body)

        elif preset_mode == "auto":
            current_mode: ScheduleMode = device.get_current_schedule_mode()

            # For reasons unknown when changing modes we need to send the proper
            # temperature also.
            if current_mode == ScheduleMode.COMFORT:
                body = {"temp": device.comfort_temp}
            elif current_mode == ScheduleMode.ECO:
                body = {"temp": device.eco_temp}
            elif device.ice_mode:
                body = {"temp": device.ice_temp}
            else:
                body = {"temp": 20}

            request_power_status = self._send_patch_request(device_id, url, args, body)

            # and then set AUTO mode.
            request_mode_status = self._send_patch_request(
                device_id, url, args, {"mode": "auto", "power": True}
            )

            return request_power_status and request_mode_status

        else:
            _LOGGER.error("Invalid HVAC_MODE: %s", preset_mode)
            return False

    def _send_patch_request(
        self,
        device_id: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        body=None,
    ) -> bool:
        """Send a patch request."""

        body["last_sync_datetime_app"] = round(time.time() * 1000)

        _LOGGER.debug("Sending patch request body: %s", body)

        response = requests.patch(
            url,
            params=params,
            json=body,
        )

        if not response:
            _LOGGER.error(
                "No response from %s while setting sending %s to %s",
                AUTH_HOST,
                str(body),
                device_id,
            )
            return False

        if response.status_code != 200:
            _LOGGER.error(
                "Got response %s from %s while setting sending %s to %s",
                response.status_code,
                AUTH_HOST,
                str(body),
                device_id,
            )
            return False

        return True
