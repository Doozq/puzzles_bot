from gradio_client import Client

client = Client("Qwen/Qwen2.5-72B-Instruct")

# Глобальный словарь контекстных буферов
context_buffers = {}


def update_user_context(user_id: int, new_entry: str, max_size: int = 500):
    global context_buffers

    if user_id not in context_buffers:
        context_buffers[user_id] = []

    context_buffers[user_id].append(new_entry)

    if len(context_buffers[user_id]) > max_size:
        context_buffers[user_id].pop(0)


def get_user_context(user_id: int) -> str:
    global context_buffers
    return "\n".join(context_buffers.get(user_id, []))


def clear_user_context(user_id: int):
    global context_buffers
    if user_id in context_buffers:
        del context_buffers[user_id]


def generate_puzzle_with_user_context(user_id: int, topic: str, difficulty: str):
    context = get_user_context(user_id)

    prompt = (
        f"Создай уникальную головоломку типа '{topic}' "
        f"с уровнем сложности '{difficulty}'.\n\n"
        f"Контекст: {context}\n"
        f"Укажи текст задачи и правильный ответ с кратким пояснением."
    )

    response = client.predict(
        prompt,
        api_name="/model_chat",
        system="Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
               "markdown в своих ответах. В своем ответе укажи только текст головоломки и ответ с пояснением, "
               "разделенные одним символом $, так, чтобы я смог сделать split текст по этому символу "
               "в список и там было 2 значения")
    puzzle_data = response[1][0][1].split("$")
    puzzle_text = puzzle_data[0]
    correct_answer = puzzle_data[1] if len(puzzle_data) > 1 else "Ответ не найден."
    update_user_context(user_id, f"Новая загадка, тема: {topic}, Сложность: {difficulty}, Задача: {puzzle_text}")

    return {
        "puzzle": puzzle_text.strip(),
        "answer": correct_answer.strip(),
    }


def generate_hint(user_id: int, puzzle_text: str):
    """
    Генерирует подсказки для головоломки.

    :param user_id: ID пользователя.
    :param puzzle_text: Текст головоломки.
    :return: Список подсказок.
    """
    context = get_user_context(user_id)

    prompt = (
        f"Дай одну короткую подсказок для следующей головоломки:\n"
        f"Головоломка: {puzzle_text}\n"
        f"Контекст: {context}"
    )

    response = client.predict(
        prompt,
        api_name="/model_chat"
    )

    hint = response[1][0][1]
    update_user_context(user_id, f"Использована подсказка: {hint}")

    return hint


def check_answer(user_id: int, puzzle_text: str, user_answer: str):
    """
    Проверяет корректность ответа пользователя на головоломку.

    :param user_id: ID пользователя.
    :param puzzle_text: Текст головоломки.
    :param user_answer: Ответ пользователя.
    :return: Результат проверки.
    """
    context = get_user_context(user_id)

    prompt = (
        f"Проверь ответ пользователя на следующую головоломку:\n"
        f"Головоломка: {puzzle_text}\n"
        f"Ответ пользователя: {user_answer}\n"
        f"Контекст: {context}\n"
        f"Сообщи, является ли ответ верным, и объясни почему. Если ответ неверный объясни почему он неверный, но не пиши правильный ответ."
    )

    response = client.predict(
        prompt,
        api_name="/model_chat",
        system="Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
               "markdown в своих ответах. Если ответ верный, помимо текста поставь знак $ в самое начало своего ответа."
               "Учитывай, что твой ответ будет напрямую отправлен пользователю, поэтому обращайся лично к нему"
    )

    ans = response[1][0][1]
    if ans[0] == "$":
        clear_user_context(user_id)
        return [1, ans[1:]]
    return [0, ans]


def generate_puzzle_with_user_info(user_id: int, user_info: str):
    context = get_user_context(user_id)

    prompt = (
        f"Создай уникальную головоломку ндля такого пользователя '{user_info}' "
        f"с уровнем сложности средний.\n\n"
        f"Контекст: {context}\n"
        f"Укажи текст задачи и правильный ответ с кратким пояснением."
    )

    response = client.predict(
        prompt,
        api_name="/model_chat",
        system="Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
               "markdown в своих ответах. В своем ответе укажи только текст головоломки и ответ с пояснением, "
               "разделенные одним символом $, так, чтобы я смог сделать split текст по этому символу "
               "в список и там было 2 значения")
    puzzle_data = response[1][0][1].split("$")
    puzzle_text = puzzle_data[0]
    correct_answer = puzzle_data[1] if len(puzzle_data) > 1 else "Ответ не найден."
    update_user_context(user_id, f"Новая загадка: {puzzle_text}")

    return {
        "puzzle": puzzle_text.strip(),
        "answer": correct_answer.strip(),
    }
