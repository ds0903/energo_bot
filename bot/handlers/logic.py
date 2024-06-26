import sqlite3


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
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute(
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

    conn.commit()
    conn.close()

    return data


async def delete_data(id):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ip_main WHERE id = ?", (id,))

    if cursor.rowcount == 1:
        data = f"ip адреса №: {id} успішно видаленно"
    else:
        data = f"ip адреси №: {id} не існує"

    conn.commit()
    conn.close()

    return data


async def list_user_ip(user_id):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ip_main WHERE user_id = ?", (user_id,))
    results = cursor.fetchall()

    cursor.close()
    conn.close()
    if results:
        return results
    else:
        return None, None, None, None, None, None, None, None


async def list_user_ip_by_id(id):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ip_main WHERE id = ?", (id,))
    results = cursor.fetchone()

    cursor.close()
    conn.close()
    if results:
        return results
    else:
        return None, None, None, None, None, None, None, None


async def update_user_ip(data):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()
    ip_id, new_ip, new_description = data
    cursor.execute(
        "UPDATE ip_main SET ip = ?, description = ? WHERE id = ?",
        (new_ip, new_description, ip_id),
    )
    conn.commit()

    cursor.close()
    conn.close()


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
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute(
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

    conn.commit()
    conn.close()

    return data


async def delete_active_user_ip(id):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM active_users_ip WHERE id = ?", (id,))

    if cursor.rowcount == 1:
        data = f"ip адреса успішно видаленно"
    else:
        data = f"ip адреси не існує"

    conn.commit()
    conn.close()

    return data


async def list_user_active_ip(user_id):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM active_users_ip WHERE user_id = ?", (user_id,))
    results = cursor.fetchall()

    cursor.close()
    conn.close()
    if results:
        return results
    else:
        return None, None, None, None, None, None, None, None, None


async def update_user_status(is_active, id, user_id, ip):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE active_users_ip SET is_active = ? WHERE user_id = ? AND ip = ? AND id = ?",
        (is_active, user_id, ip, id),
    )
    conn.commit()

    cursor.close()
    conn.close()
