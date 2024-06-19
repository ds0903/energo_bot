import sqlite3


async def insert_data(data):
    conn = sqlite3.connect("energo_bot.db")
    cursor = conn.cursor()

    clas, description = data

    cursor.execute(
        "INSERT OR IGNORE INTO user_ip (clas, description) VALUES (?, ?)",
        (clas, description),
    )
    # data = cursor.fetchone()

    if cursor.rowcount == 1:
        data = "Рецепт успішно додано"
    else:
        data = "Рецепт вже інсує"

    conn.commit()
    conn.close()

    return data
