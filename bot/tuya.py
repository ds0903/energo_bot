"""Мінімальний клієнт Tuya Cloud OpenAPI: лише читання статусу пристроїв.

Підпис запитів: https://developer.tuya.com/en/docs/iot/new-singnature?id=Kbw0q34cs2e5g
"""

import asyncio
import hashlib
import hmac
import os
import time
import uuid

import aiohttp
from yarl import URL

# Central Europe Data Center; інші: openapi-weaz.tuyaeu.com (Western Europe),
# openapi.tuyaus.com (Western America), openapi.tuyacn.com (China), openapi.tuyain.com (India)
DEFAULT_ENDPOINT = "https://openapi.tuyaeu.com"

EMPTY_BODY_SHA256 = hashlib.sha256(b"").hexdigest()
# 1010 - токен недійсний, 1011 - токен прострочений
TOKEN_ERROR_CODES = {1010, 1011}
DEVICES_PATH = "/v1.0/iot-01/associated-users/devices"
DEVICES_PAGE_SIZE = 100
MAX_DEVICE_PAGES = 10


class TuyaError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class TuyaClient:
    def __init__(self, access_id, access_secret, endpoint=DEFAULT_ENDPOINT):
        self.access_id = access_id
        self.access_secret = access_secret
        self.endpoint = endpoint.rstrip("/")
        self._token = None
        self._token_expires = 0.0
        self._token_lock = asyncio.Lock()
        self._session = None

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    def _sign_headers(self, method, url, token):
        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        string_to_sign = f"{method}\n{EMPTY_BODY_SHA256}\n\n{url}"
        message = self.access_id + (token or "") + t + nonce + string_to_sign
        sign = (
            hmac.new(self.access_secret.encode(), message.encode(), hashlib.sha256)
            .hexdigest()
            .upper()
        )
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "t": t,
            "nonce": nonce,
        }
        if token:
            headers["access_token"] = token
        return headers

    async def _call(self, path, params=None, token=None):
        url = path
        if params:
            # параметри в підписі мають іти за алфавітом
            url += "?" + "&".join(f"{key}={params[key]}" for key in sorted(params))
        headers = self._sign_headers("GET", url, token)

        session = await self._get_session()
        async with session.get(
            URL(self.endpoint + url, encoded=True), headers=headers
        ) as response:
            try:
                data = await response.json(content_type=None)
            except ValueError:
                raise TuyaError(f"Некоректна відповідь Tuya (HTTP {response.status})")

        if not isinstance(data, dict):
            raise TuyaError("Некоректна відповідь Tuya")
        if not data.get("success"):
            raise TuyaError(data.get("msg") or "Помилка Tuya API", data.get("code"))
        return data["result"]

    async def _get_token(self, force=False):
        async with self._token_lock:
            if force or not self._token or time.time() >= self._token_expires - 60:
                result = await self._call("/v1.0/token", {"grant_type": 1})
                self._token = result["access_token"]
                self._token_expires = time.time() + int(result.get("expire_time", 7200))
            return self._token

    async def _api(self, path, params=None):
        token = await self._get_token()
        try:
            return await self._call(path, params, token)
        except TuyaError as error:
            if error.code not in TOKEN_ERROR_CODES:
                raise
        # токен втратив чинність раніше за розклад - беремо новий і повторюємо
        token = await self._get_token(force=True)
        return await self._call(path, params, token)

    async def list_devices(self):
        """Усі пристрої акаунтів, прив'язаних до проєкту: [{"id", "name", "online"}, ...].

        Один запит дає і перелік, і статус онлайн, тож додатково опитувати кожен
        пристрій окремо не потрібно.
        """
        devices = []
        last_row_key = None
        for _ in range(MAX_DEVICE_PAGES):
            params = {"size": DEVICES_PAGE_SIZE}
            if last_row_key:
                params["last_row_key"] = last_row_key
            result = await self._api(DEVICES_PATH, params)
            for device in result.get("devices", []):
                if "id" in device and "online" in device:
                    devices.append(
                        {
                            "id": device["id"],
                            "name": device.get("name") or "",
                            "online": bool(device["online"]),
                        }
                    )
            last_row_key = result.get("last_row_key")
            if not result.get("has_more") or not last_row_key:
                break
        return devices


_client = None


def get_client():
    """Клієнт за ключами з .env або None, якщо Tuya не налаштовано."""
    global _client
    if _client is None:
        access_id = (os.getenv("TUYA_ACCESS_ID") or "").strip()
        access_secret = (os.getenv("TUYA_ACCESS_SECRET") or "").strip()
        if not access_id or not access_secret:
            return None
        endpoint = (os.getenv("TUYA_ENDPOINT") or "").strip() or DEFAULT_ENDPOINT
        _client = TuyaClient(access_id, access_secret, endpoint)
    return _client
