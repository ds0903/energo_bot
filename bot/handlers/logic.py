import sqlite3


async def insert_data(user_id, ip, ip_description, first_name, username):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    # clas, description = data

    cursor.execute(
        "INSERT OR IGNORE INTO ip_main (user_id, ip, description, first_name, username) VALUES (?, ?, ?, ?, ?)", (user_id, ip, ip_description, first_name, username),
    )
    # data = cursor.fetchone()

    if cursor.rowcount == 1:
        data = "ip адрес успішно додано"
    else:
        data = "ip адрес вже інсує"

    conn.commit()
    conn.close()

    return data
 