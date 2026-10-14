"""Push-канал Tuya (MQTT open-hub): Tuya сама повідомляє, коли пристрій став online/offline.

Формат повідомлень і розшифрування відповідають офіційному tuya-iot-py-sdk (openmq.py, device.py).
Канал лише будить моніторинг, а сам стан завжди підтверджується запитом до API.
"""

import asyncio
import base64
import json
import logging
import threading
from urllib.parse import urlsplit

import paho.mqtt.client as mqtt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from settings import push_log_raw
from tuya import TuyaError

logger = logging.getLogger(__name__)

GCM_TAG_LENGTH = 16
PROTOCOL_REPORT = 4  # звіти про значення (DP) пристрою: світло/розетка/датчики
# у різних версіях платформи подію називають по-різному: online / deviceOnline
ONLINE_CODES = {"online", "deviceonline"}
OFFLINE_CODES = {"offline", "deviceoffline"}
# коли конфіг не вдалося отримати, пробуємо знову через стільки секунд
RETRY_SECONDS = (30, 60, 120, 300)


def decrypt_message(b64: str, password: str, t) -> dict:
    """Розшифровує поле data повідомлення (AES-128-GCM, msg_encrypted_version 2.0).

    Ключ - символи 8..23 пароля з конфігу MQTT; буфер: 4 байти довжини IV (big-endian),
    IV, шифротекст, 16 байт тегу; AAD - значення поля t.
    """
    key = password[8:24].encode("utf-8")
    buffer = base64.b64decode(b64)
    iv_length = int.from_bytes(buffer[0:4], byteorder="big")
    nonce = buffer[4 : 4 + iv_length]
    # AESGCM очікує шифротекст разом із тегом наприкінці
    sealed = buffer[4 + iv_length :]
    if len(sealed) < GCM_TAG_LENGTH:
        raise ValueError("повідомлення замале")
    plaintext = AESGCM(key).decrypt(nonce, sealed, str(t).encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))


def parse_status_event(payload: bytes | str, password: str):
    """Розбирає MQTT-повідомлення.

    Повертає (device_id, online): online=True/False для подій online/offline, а None
    для будь-якого іншого службового повідомлення пристрою (формат могли змінити, тож
    це лише сигнал перевірити стан через API). Звіти про значення (protocol 4),
    некоректні, чужі чи пошкоджені повідомлення дають None замість винятку.
    """
    try:
        message = json.loads(payload)
        data = decrypt_message(message["data"], password, message.get("t", ""))
    except (ValueError, KeyError, TypeError, InvalidTag):
        logger.warning("Не вдалося розібрати повідомлення Tuya", exc_info=True)
        return None

    if push_log_raw():
        logger.info(
            "Push Tuya RAW розшифровано (protocol=%s): %s",
            message.get("protocol") if isinstance(message, dict) else "?",
            json.dumps(data, ensure_ascii=False),
        )

    if not isinstance(data, dict):
        return None
    protocol = message.get("protocol")
    if protocol == PROTOCOL_REPORT:
        logger.debug("Push Tuya: звіт про значення пристрою (ігнорую)")
        return None

    biz_data = data.get("bizData")
    device_id = (
        data.get("devId")
        or (biz_data.get("devId") if isinstance(biz_data, dict) else None)
        or message.get("devId")
    )
    biz_code = str(data.get("bizCode") or "").lower()
    if not device_id:
        logger.info(
            "Push Tuya: повідомлення без devId (protocol=%s bizCode=%s поля=%s), ігнорую",
            protocol,
            biz_code or "-",
            sorted(data),
        )
        return None
    if biz_code in ONLINE_CODES:
        return device_id, True
    if biz_code in OFFLINE_CODES:
        return device_id, False

    # невідома подія пристрою: не вгадуємо стан, а просимо перевірити його в API
    logger.info(
        "Push Tuya: невідома подія пристрою …%s (protocol=%s bizCode=%s поля=%s)",
        str(device_id)[-4:],
        protocol,
        biz_code or "-",
        sorted(data),
    )
    return device_id, None


class TuyaPush:
    """Тримає MQTT-з'єднання з Tuya і передає події online/offline в asyncio."""

    def __init__(self, client, loop, on_event):
        # on_event(device_id: str, online: bool | None) викликається в потоці циклу
        # asyncio; online=None означає "щось сталося, стан перевір через API"
        self.client = client
        self.loop = loop
        self.on_event = on_event
        self.connected = threading.Event()
        self._mqtt = None

    def _on_connect(self, mqttc, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            logger.warning("Push Tuya: з'єднання відхилено (%s)", reason_code)
            return
        for topic in userdata["topics"]:
            mqttc.subscribe(topic)
        self.connected.set()
        logger.info("Push Tuya: підключено, очікую події пристроїв")

    def _on_disconnect(self, mqttc, userdata, flags, reason_code, properties=None):
        self.connected.clear()
        if reason_code != 0:
            logger.warning(
                "Push Tuya: з'єднання втрачено (%s), перепідключення", reason_code
            )

    def _on_message(self, mqttc, userdata, msg):
        if push_log_raw():
            logger.info(
                "Push Tuya RAW повідомлення (топік %s): %s",
                msg.topic,
                msg.payload.decode("utf-8", "replace"),
            )
        event = parse_status_event(msg.payload, userdata["password"])
        if event is None:
            return
        device_id, online = event
        label = {True: "online", False: "offline", None: "подія (стан невідомий)"}
        logger.info("Push Tuya: пристрій …%s %s", device_id[-4:], label[online])
        self.loop.call_soon_threadsafe(self.on_event, device_id, online)

    def _connect(self, config: dict):
        topics = list((config.get("source_topic") or {}).values())
        if not topics:
            raise TuyaError("Tuya не повернула топіки для підписки")

        mqttc = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=config["client_id"]
        )
        mqttc.username_pw_set(config["username"], config["password"])
        mqttc.user_data_set({"password": config["password"], "topics": topics})
        mqttc.on_connect = self._on_connect
        mqttc.on_disconnect = self._on_disconnect
        mqttc.on_message = self._on_message
        mqttc.reconnect_delay_set(min_delay=2, max_delay=60)

        url = urlsplit(config["url"])
        if url.scheme in ("ssl", "mqtts", "tls"):
            mqttc.tls_set()
        mqttc.connect_async(url.hostname, url.port or 8883)
        mqttc.loop_start()
        return mqttc

    def _disconnect(self):
        mqttc, self._mqtt = self._mqtt, None
        self.connected.clear()
        if mqttc is not None:
            mqttc.disconnect()
            mqttc.loop_stop()

    async def run(self):
        """Підтримує канал: бере конфіг, підключається і оновлює його до закінчення терміну."""
        attempt = 0
        try:
            while True:
                try:
                    config = await self.client.get_mq_config()
                    self._disconnect()
                    self._mqtt = self._connect(config)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    delay = RETRY_SECONDS[min(attempt, len(RETRY_SECONDS) - 1)]
                    attempt += 1
                    logger.warning(
                        "Push Tuya: не вдалося підключитися, повтор через %s с",
                        delay,
                        exc_info=True,
                    )
                    await asyncio.sleep(delay)
                    continue

                attempt = 0
                # облікові дані діють обмежений час, тож оновлюємо їх заздалегідь
                lifetime = int(config.get("expire_time") or 7200)
                await asyncio.sleep(max(300, lifetime - 120))
        finally:
            self._disconnect()
