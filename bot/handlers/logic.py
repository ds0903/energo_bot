import sqlite3


<<<<<<< HEAD
async def insert_data(user_id, ip, ip_description, first_name, last_name, username, language_code, is_premium,):
=======
async def insert_data(user_id, ip, ip_description, first_name, username):
>>>>>>> 4b9c29fa1e67d5ec4f451a0e7b4a58045946b152
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    # clas, description = data

    cursor.execute(
<<<<<<< HEAD
        "INSERT OR IGNORE INTO ip_main (user_id, ip, description, first_name, last_name, username, language_code, is_premium) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (user_id, ip, ip_description, first_name, last_name, username, language_code, is_premium)
=======
        "INSERT OR IGNORE INTO ip_main (user_id, ip, description, first_name, username) VALUES (?, ?, ?, ?, ?)", (user_id, ip, ip_description, first_name, username),
>>>>>>> 4b9c29fa1e67d5ec4f451a0e7b4a58045946b152
    )
    # data = cursor.fetchone()

    if cursor.rowcount == 1:
        data = "ip адрес успішно додано"
    else:
        data = "ip адрес вже інсує"

    conn.commit()
    conn.close()

    return data
<<<<<<< HEAD


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
    cursor.execute("UPDATE ip_main SET ip = ?, description = ? WHERE id = ?", (new_ip, new_description, ip_id))
    conn.commit()

    cursor.close()
    conn.close()
=======
 
>>>>>>> 4b9c29fa1e67d5ec4f451a0e7b4a58045946b152
