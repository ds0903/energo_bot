import aiosqlite

datab2 = "energo_bot.db"
# datab2 = "/home/ubuntu/energo_bot.db"


async def insert_data(
    user_id,
    ip,
    ip_description,
    first_name,
    last_name,
    username,
    language_code,
    is_premium,
):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "INSERT OR IGNORE INTO ip_main (user_id, ip, description, first_name, last_name, username, language_code, is_premium) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    ip,
                    ip_description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                ),
            )

            if cursor.rowcount == 1:
                data = "ip адрес успішно додано"
            else:
                data = "ip адрес вже інсує"

            await conn.commit()

            return data


async def delete_data(id):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("DELETE FROM ip_main WHERE id = ?", (id,))
            deleted = cursor.rowcount
            # видалена IP-адреса не повинна далі пінгуватися
            await cursor.execute("DELETE FROM active_users_ip WHERE id = ?", (id,))

            if deleted == 1:
                data = f"IP-адресу №: {id} успішно видаленно"
            else:
                data = f"IP-адреси №: {id} не існує"

            await conn.commit()

            return data


async def list_user_ip(user_id):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("SELECT * FROM ip_main WHERE user_id = ?", (user_id,))
            return await cursor.fetchall()


async def list_user_ip_by_id(id):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("SELECT * FROM ip_main WHERE id = ?", (id,))
            return await cursor.fetchone()


# хранение активних ip адресов для пингования
async def insert_active_user_ip(
    id,
    user_id,
    ip,
    ip_description,
    first_name,
    last_name,
    username,
    language_code,
    is_premium,
):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "INSERT OR IGNORE INTO active_users_ip (id, user_id, ip, description, first_name, last_name, username, language_code, is_premium) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    id,
                    user_id,
                    ip,
                    ip_description,
                    first_name,
                    last_name,
                    username,
                    language_code,
                    is_premium,
                ),
            )

            if cursor.rowcount == 1:
                data = "ip адрес успішно додано"
            else:
                data = "ip адрес вже інсує"

            await conn.commit()

            return data


async def delete_active_user_ip(id):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("DELETE FROM active_users_ip WHERE id = ?", (id,))

            if cursor.rowcount == 1:
                data = "IP-адресу успішно видаленно"
            else:
                data = "IP-адреси не існує"

            await conn.commit()

            return data


async def list_user_active_ip(user_id):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "SELECT * FROM active_users_ip WHERE user_id = ?", (user_id,)
            )
            return await cursor.fetchall()


async def update_user_status(is_active, user_id, id, ip):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "UPDATE active_users_ip SET is_active = ? WHERE user_id = ? AND ip = ? AND id = ?",
                (is_active, user_id, ip, id),
            )
            await conn.commit()


async def add_gosti(
    user_id,
    is_bot,
    first_name,
    last_name,
    username,
    language_code,
    is_premium,
    added_to_attachment_menu,
    can_join_groups,
    can_read_all_group_messages,
    supports_inline_queries,
    can_connect_to_business,
    сurrent_time,
):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("SELECT * FROM gosti WHERE user_id = ?", (user_id,))

            existing_user = await cursor.fetchone()

            if existing_user:
                data = "Користувач вже існує в базі даних"
            else:
                await cursor.execute(
                    "INSERT INTO gosti (user_id, is_bot, first_name, last_name, username, language_code, is_premium, added_to_attachment_menu, can_join_groups, can_read_all_group_messages, supports_inline_queries, can_connect_to_business, сurrent_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        is_bot,
                        first_name,
                        last_name,
                        username,
                        language_code,
                        is_premium,
                        added_to_attachment_menu,
                        can_join_groups,
                        can_read_all_group_messages,
                        supports_inline_queries,
                        can_connect_to_business,
                        сurrent_time,
                    ),
                )

                if cursor.rowcount == 1:
                    data = "Користувач успішно доданий"
                else:
                    data = "Помилка при додаванні користувача"

            await conn.commit()

            return data


async def list_admin_info(status):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            if status == "1":  # Всі активні ip користувача
                await cursor.execute("SELECT * FROM active_users_ip")
            elif status == "2":  # Всі користувачі в базі
                await cursor.execute("SELECT * FROM ip_main")
            elif status == "3":  # Відвідувачі
                await cursor.execute("SELECT * FROM gosti")
            else:
                return []
            return await cursor.fetchall()


# ---- режими роботи та моніторинг світла через Tuya (стандартний режим)

MODE_STANDARD = "standard"
MODE_EXTENDED = "extended"


async def init_db():
    """Створює таблиці стандартного режиму, якщо їх ще немає."""
    async with aiosqlite.connect(datab2) as conn:
        await conn.executescript("""
            -- таблиці початкової версії (схема збігається з уже наявними базами),
            -- щоб бот стартував і на порожній базі нового сервера
            CREATE TABLE IF NOT EXISTS ip_main (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ip TEXT NOT NULL,
                description TEXT,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language_code TEXT,
                is_premium TEXT
            );
            CREATE TABLE IF NOT EXISTS active_users_ip (
                id INTEGER UNIQUE,
                user_id INTEGER,
                ip TEXT,
                description TEXT,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language_code TEXT,
                is_premium BOOLEAN,
                is_active BOOLEAN DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS gosti (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                is_bot BOOLEAN,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language_code TEXT,
                is_premium BOOLEAN,
                added_to_attachment_menu BOOLEAN,
                can_join_groups BOOLEAN,
                can_read_all_group_messages BOOLEAN,
                supports_inline_queries BOOLEAN,
                can_connect_to_business BOOLEAN,
                сurrent_time TEXT
            );
            CREATE TABLE IF NOT EXISTS user_modes (
                user_id INTEGER PRIMARY KEY,
                mode TEXT NOT NULL,
                notify INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS tuya_state (
                device_id TEXT PRIMARY KEY,
                online INTEGER NOT NULL,
                since TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS panels (
                user_id INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL
            );
            """)
        # таблиця могла бути створена попередньою версією без колонки notify
        async with conn.execute("PRAGMA table_info(user_modes)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "notify" not in columns:
            await conn.execute(
                "ALTER TABLE user_modes ADD COLUMN notify INTEGER NOT NULL DEFAULT 1"
            )
        await conn.commit()


async def get_user_mode(user_id):
    """Режим користувача або None, якщо він ще не вибирав."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT mode FROM user_modes WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]

            # ті, хто вже користувався моніторингом IP-адрес, лишаються в розширеному
            await cursor.execute(
                "SELECT 1 FROM ip_main WHERE user_id = ? LIMIT 1", (user_id,)
            )
            if await cursor.fetchone():
                await cursor.execute(
                    "INSERT OR IGNORE INTO user_modes (user_id, mode) VALUES (?, ?)",
                    (user_id, MODE_EXTENDED),
                )
                await conn.commit()
                return MODE_EXTENDED
            return None


async def set_user_mode(user_id, mode):
    async with aiosqlite.connect(datab2) as conn:
        # upsert, а не REPLACE, щоб зміна режиму не скидала налаштування сповіщень
        await conn.execute(
            "INSERT INTO user_modes (user_id, mode) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET mode = excluded.mode",
            (user_id, mode),
        )
        await conn.commit()


async def get_notifications(user_id):
    """Чи увімкнені сповіщення про світло (за замовчуванням так)."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT notify FROM user_modes WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else True


async def set_notifications(user_id, enabled):
    async with aiosqlite.connect(datab2) as conn:
        await conn.execute(
            "UPDATE user_modes SET notify = ? WHERE user_id = ?",
            (int(enabled), user_id),
        )
        await conn.commit()


async def list_mode_user_ids():
    """Усі, хто користується ботом (мають режим): їм адмін може розіслати нову панель."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM user_modes ORDER BY user_id")
            return [row[0] for row in await cursor.fetchall()]


async def list_notify_user_ids():
    """Користувачі стандартного режиму з увімкненими сповіщеннями про світло."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id FROM user_modes WHERE mode = ? AND notify = 1",
                (MODE_STANDARD,),
            )
            return [row[0] for row in await cursor.fetchall()]


async def get_panel(user_id):
    """id повідомлення-панелі користувача (єдиного повідомлення бота в чаті) або None."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT message_id FROM panels WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_panel(user_id, message_id):
    async with aiosqlite.connect(datab2) as conn:
        await conn.execute(
            "INSERT INTO panels (user_id, message_id) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET message_id = excluded.message_id",
            (user_id, message_id),
        )
        await conn.commit()


async def get_tuya_state(device_id):
    """(online, since) або None, якщо стан ще не фіксувався."""
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT online, since FROM tuya_state WHERE device_id = ?",
                (device_id,),
            )
            row = await cursor.fetchone()
            return (bool(row[0]), row[1]) if row else None


async def set_tuya_state(device_id, online, since):
    async with aiosqlite.connect(datab2) as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO tuya_state (device_id, online, since) VALUES (?, ?, ?)",
            (device_id, int(online), since),
        )
        await conn.commit()
