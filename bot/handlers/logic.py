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

            if cursor.rowcount == 1:
                data = f"ip адреса №: {id} успішно видаленно"
            else:
                data = f"ip адреси №: {id} не існує"

            await conn.commit()

            return data


async def list_user_ip(user_id):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("SELECT * FROM ip_main WHERE user_id = ?", (user_id,))
            results = await cursor.fetchall()

            if results:
                return results
            else:
                return None, None, None, None, None, None, None, None


async def list_user_ip_by_id(id):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute("SELECT * FROM ip_main WHERE id = ?", (id,))
            results = await cursor.fetchone()

            if results:
                return results
            else:
                return None, None, None, None, None, None, None, None


async def update_user_ip(data):
    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:
            ip_id, new_ip, new_description = data
            await cursor.execute(
                "UPDATE ip_main SET ip = ?, description = ? WHERE id = ?",
                (new_ip, new_description, ip_id),
            )
            await conn.commit()

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
                data = f"IP-адресу успішно видаленно"
            else:
                data = f"IP-адреси не існує"

            await conn.commit()

            return data


async def list_user_active_ip(user_id):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "SELECT * FROM active_users_ip WHERE user_id = ?", (user_id,)
            )
            results = await cursor.fetchall()

            if results:
                return results
            else:
                return None, None, None, None, None, None, None, None, None


async def update_user_status(is_active, user_id, id, ip):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "UPDATE active_users_ip SET is_active = ? WHERE user_id = ? AND ip = ? AND id = ?",
                (is_active, user_id, ip, id),
            )
            await conn.commit()


async def get_is_active(user_id, id):

    async with aiosqlite.connect(datab2) as conn:
        async with conn.cursor() as cursor:

            await cursor.execute(
                "SELECT is_active FROM active_users_ip WHERE user_id = ? AND id = ?",
                (user_id, id),
            )
            result = await cursor.fetchone()

            await conn.commit()

            return result


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
                return None
            results = await cursor.fetchall()

            if results:
                return results
            else:
                return None
