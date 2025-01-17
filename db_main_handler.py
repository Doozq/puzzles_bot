import sqlite3
import datetime

DB_FILE = "app_database.db"


def initialize_database():
    """
    Инициализирует базу данных, создавая таблицы 'users' и 'logs', если они еще не существуют.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Создаем таблицу для пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, 
            full_name TEXT NOT NULL,
            hobbies TEXT,
            rating REAL DEFAULT 0.0,
            have_active_task BOOLEAN DEFAULT FALSE
        )
    ''')

    # Создаем таблицу для логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_text TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_text TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    connection.commit()
    connection.close()

def add_user(user_id: int, full_name: str, hobbies: str, rating: float = 0.0):
    """
    Добавляет нового пользователя в таблицу 'users', если он еще не существует.

    :param user_id: Telegram ID пользователя.
    :param full_name: ФИО пользователя.
    :param hobbies: Увлечения пользователя.
    :param rating: Рейтинг пользователя.
    """
    if user_exists(user_id):
        raise ValueError(f"Пользователь с ID {user_id} уже существует.")

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO users (id, full_name, hobbies, rating)
        VALUES (?, ?, ?, ?)
    ''', (user_id, full_name, hobbies, rating))

    connection.commit()
    connection.close()
    add_log(user_id, "Юзер зарегистрировался")

def user_exists(user_id: int) -> bool:
    """
    Проверяет, существует ли пользователь с указанным Telegram ID.

    :param user_id: Telegram ID пользователя.
    :return: True, если пользователь существует, иначе False.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        SELECT EXISTS(SELECT 1 FROM users WHERE id = ?)
    ''', (user_id,))

    exists = cursor.fetchone()[0]
    connection.close()

    return bool(exists)

def add_log(user_id: int, log_text: str):
    """
    Добавляет запись в лог для указанного пользователя.

    :param user_id: Telegram ID пользователя.
    :param log_text: Текст лога.
    """

    log_text = f"{log_text}\n{str(datetime.datetime.now())}"
    if not user_exists(user_id):
        raise ValueError(f"Пользователь с ID {user_id} не существует.")

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO logs (user_id, log_text)
        VALUES (?, ?)
    ''', (user_id, log_text))

    connection.commit()
    connection.close()


def get_leaderboard(limit: int = 5):
    """
    Получает список лидеров по рейтингу.

    :param limit: Максимальное количество лидеров для отображения.
    :return: Список пар (ФИО пользователя, рейтинг), отсортированных по убыванию рейтинга.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        SELECT full_name, rating, id
        FROM users
        ORDER BY rating DESC
        LIMIT ?
    ''', (limit,))

    leaderboard = cursor.fetchall()
    connection.close()

    # Преобразуем результат в список словарей
    return [{"full_name": user[0], "rating": user[1], "id": user[2]} for user in leaderboard]


def has_active_task(user_id: int):
    """
    Проверяет, есть ли у юзера активная задача

    :param user_id:
    :return: true/false - наличие задачи
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('SELECT have_active_task FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()

    connection.close()

    if result is None:
        raise ValueError("Пользователь не найден!")
    return result[0]


def set_active_task(user_id: int, is_active: bool):
    """
    Изменяет значение активной задачи пользователя на нужное
    :param user_id:
    :param is_active:
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('UPDATE users SET have_active_task = ? WHERE id = ?', (is_active, user_id))

    connection.commit()
    connection.close()
    add_log(user_id, f"У Пользователя с айди {user_id} значение активной задачи поменялось на {is_active}")


def add_finished_task(user_id: int, task_text: str):
    """
    Добавляет решенную задачу в копилку юзера.
    :param user_id: ID пользователя
    :param task_text: Текст задачи
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        INSERT INTO tasks (user_id, task_text)
        VALUES (?, ?)
    ''', (user_id, task_text))

    connection.commit()
    connection.close()
    add_log(user_id, f"Пользвоатель с айди {user_id} успешно завершил задачу")

def get_all_finished_tasks(user_id: int):
    """
    Получение мапы решенных юзером задач
    :param user_id:
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        SELECT id, task_text 
        FROM tasks
        WHERE user_id = ?
    ''', (user_id,))

    tasks = cursor.fetchall()

    connection.close()
    result = [{task[0]: task[1]} for task in tasks]

    return result


def get_user_rating(user_id: int) -> float:
    """
    Получает рейтинг пользователя по его ID.

    :param user_id: ID пользователя.
    :return: Рейтинг пользователя.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        SELECT rating FROM users WHERE id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    connection.close()

    if result is None:
        raise ValueError(f"Пользователь с ID {user_id} не найден.")

    return result[0]

def set_user_rating(user_id: int, new_rating: float):
    """
    Обновляет рейтинг пользователя.

    :param user_id: ID пользователя.
    :param new_rating: Новый рейтинг пользователя.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        UPDATE users SET rating = ? WHERE id = ?
    ''', (new_rating, user_id))

    connection.commit()
    connection.close()
    add_log(user_id, f"Рейтинг пользователя с айди {user_id} изменился и стал равен {new_rating}")


def get_all_users():
    # Пример для SQLite
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users