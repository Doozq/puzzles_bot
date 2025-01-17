import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types, Router, BaseMiddleware
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup
from config import category_names, difficulty_names
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from puzzle_generation import generate_puzzle_with_user_context, check_answer, generate_hint, clear_user_context
from db_main_handler import initialize_database, add_user, get_leaderboard, get_user_rating, set_user_rating, add_log, user_exists, add_user, get_all_users
# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен Telegram-бота
API_TOKEN = "7898792093:AAGJq48M50ewbEqyk0j4M70Z9d1XX41o0-w"

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Состояния для FSM
class PuzzleState(StatesGroup):
    choosing_category = State()
    choosing_difficulty = State()
    solving_puzzle = State()
    writing_feedback = State()
    registering_name = State()
    registering_hobby = State()


class CheckRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        message = data['event_update'].message
        user_id = message.chat.id
        state: FSMContext = data['state']
        
        # Если команда /start, пропускаем
        if message.text == '/start':
            return await handler(event, data)

        current_state = await state.get_state()

        # Если пользователь в процессе регистрации (состояния регистрации), пропускаем
        if current_state in [PuzzleState.registering_name.state, PuzzleState.registering_hobby.state]:
            return await handler(event, data)

        # Проверяем, зарегистрирован ли пользователь
        if not user_exists(user_id):
            await bot.send_message(chat_id=user_id, text="Вы не зарегистрированы! Зарегистрируйтесь, используя команду /start.")
            return  # Не передаем управление дальше

        # Если все проверки пройдены, вызываем обработчик
        return await handler(event, data)


# Функция для создания клавиатуры с кнопками
def get_main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Получить новую головоломку")],
            [KeyboardButton(text="Таблица лидеров")],
            [KeyboardButton(text="Профиль")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False 
    )

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    
    user_id = message.from_user.id

    if not user_exists(user_id):
        await message.answer("Добро пожаловать! Похоже, вы здесь впервые.\nПожалуйста, введите ваше ФИО для регистрации.")
        await state.set_state(PuzzleState.registering_name)
    else:
        await message.answer("Добро пожаловать обратно! Вы можете начать с выбора задачи.")


@router.message(PuzzleState.registering_name)
async def handle_registration_name(message: types.Message, state: FSMContext):
    full_name = message.text

    await state.update_data(full_name=full_name)
    await message.answer("Спасибо! Теперь укажите ваше хобби.")
    await state.set_state(PuzzleState.registering_hobby)


@router.message(PuzzleState.registering_hobby)
async def handle_registration_hobby(message: types.Message, state: FSMContext):
    hobby = message.text
    user_id = message.from_user.id

    data = await state.get_data()
    full_name = data.get("full_name")

    add_user(user_id, full_name, hobby)
    keyboard = get_main_menu_keyboard()
    await message.answer(f"Спасибо, {full_name}! Вы успешно зарегистрированы.\nВаше хобби: {hobby}", reply_markup=keyboard)
    await state.clear()


@router.message(lambda message: message.text == "Таблица лидеров")
async def show_leaderboard(message: types.Message, state: FSMContext):
    leaderboard = get_leaderboard()

    leaderboard_text = "\n".join([f"{i + 1}. {user['full_name']} - {user['rating']}" for i, user in enumerate(leaderboard)])

    await message.answer(f"Таблица лидеров:\n{leaderboard_text}")


@router.message(lambda message: message.text == "Профиль")
async def show_leaderboard(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    leaderboard = get_leaderboard(limit=1000)

    for i, user in enumerate(leaderboard):
        if user["id"] == user_id:
            await message.answer(f"ФИО: {user['full_name']}\nРейтинг: {user['rating']}\nМесто в рейтинге: {i+1}")
            break

    
# Обработчик для кнопки "Получить новую головоломку"
@router.callback_query(lambda c: c.data in ["choose_cat", "new_puzzle"])
async def get_new_puzzle(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == PuzzleState.solving_puzzle.state:
        await callback_query.message.answer("Вы не можете получить новую задачу пока не решите или не отмените начатую")
        await callback_query.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Логика", callback_data="logic")],
        [InlineKeyboardButton(text="Шарады", callback_data="charades")],
        [InlineKeyboardButton(text="Загадки", callback_data="riddles")],
        [InlineKeyboardButton(text="Математика", callback_data="math")],
        [InlineKeyboardButton(text="Ассоциации", callback_data="associations")],
        [InlineKeyboardButton(text="Случайная", callback_data="random")],
    ])
    if callback_query.data == "choose_cat":
        await callback_query.message.edit_text("Выберите тип головоломки:", reply_markup=keyboard)
    else:
        await callback_query.message.answer("Выберите тип головоломки:", reply_markup=keyboard)
    await state.set_state(PuzzleState.choosing_category)
    await callback_query.answer()

# Выбор категории
@router.message(lambda message: message.text == "Получить новую головоломку")
async def choose_category(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == PuzzleState.solving_puzzle.state:
        await message.answer("Вы не можете получить новую задачу пока не решите или не отмените начатую")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Логика", callback_data="logic")],
        [InlineKeyboardButton(text="Шарады", callback_data="charades")],
        [InlineKeyboardButton(text="Загадки", callback_data="riddles")],
        [InlineKeyboardButton(text="Математика", callback_data="math")],
        [InlineKeyboardButton(text="Ассоциации", callback_data="associations")],
        [InlineKeyboardButton(text="Случайная", callback_data="random")],
    ])
    await message.answer(
        "Выберите тип головоломки:",
        reply_markup=keyboard
    )
    await state.set_state(PuzzleState.choosing_category)

# Обработка выбора категории
@router.callback_query(lambda c: c.data in ["logic", "charades", "riddles", "math", "random", "associations"])
async def choose_difficulty(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == PuzzleState.solving_puzzle.state:
        await callback_query.message.answer("Вы не можете получить новую задачу пока не решите или не отмените начатую")
        await callback_query.answer()
        return
    category = callback_query.data
    if category == "random":
        category = random.choice(list(category_names.keys()))

    await state.update_data(category=category)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Легкий", callback_data="easy")],
        [InlineKeyboardButton(text="Средний", callback_data="medium")],
        [InlineKeyboardButton(text="Сложный", callback_data="hard")],
        [InlineKeyboardButton(text="Назад", callback_data="choose_cat")]
    ])
    
    category_name = category_names[category]
    await callback_query.message.edit_text(f"Выберите сложность головоломки из категории {category_name}:", reply_markup=keyboard)
    await state.set_state(PuzzleState.choosing_difficulty)
    await callback_query.answer()

# Обработка выбора сложности
@router.callback_query(lambda c: c.data in ["easy", "medium", "hard"])
async def type_puzzle(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == PuzzleState.solving_puzzle.state:
        await callback_query.message.answer("Вы не можете получить новую задачу пока не решите или не отмените начатую")
        await callback_query.answer()
        return
    difficulty = callback_query.data
    difficulty_name = difficulty_names[difficulty]
    data = await state.get_data()
    category = data.get('category')
    category_name = category_names[category]
    user_id = callback_query.from_user.id

    puzzle_data = generate_puzzle_with_user_context(user_id, category_names[category], difficulty_names[difficulty])
    puzzle_text, correct_answer = puzzle_data["puzzle"], puzzle_data["answer"]
    await state.update_data(difficulty=difficulty, current_puzzle=puzzle_text, correct_answer=correct_answer, score=0)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Получить подсказку", callback_data="hint")],
        [InlineKeyboardButton(text="Отказаться", callback_data="cancel")]
    ])
    
    if "attempts_left" not in data:
        await state.update_data(attempts_left=3)  # 3 попытки для решения задачи

    await callback_query.message.edit_text(
        f"Головоломка\nТип: {category_name}\nСложность: {difficulty_name}\n\n{puzzle_text}\n\nВведите ваш ответ:",
        reply_markup=keyboard
    )
    await state.set_state(PuzzleState.solving_puzzle)
    await callback_query.answer()


# Ожидание ответа от пользователя
@router.message(PuzzleState.solving_puzzle)
async def process_user_answer(message: types.Message, state: FSMContext):
    
    await message.answer("Проверяем ваш ответ, ожидайте")
    
    user_answer = message.text
    data = await state.get_data()
    puzzle_text = data.get("current_puzzle")
    attempts_left = data.get("attempts_left", 3)  # Количество оставшихся попыток
    score = data.get("score")
    user_id = message.from_user.id

    # Проверка ответа
    is_correct, comment = check_answer(user_id, puzzle_text, user_answer)  # Функция для проверки ответа

    # Если ответ правильный
    if is_correct:
        difficulty = data.get("difficulty")
        diff_points = {
            "easy": 1,
            "medium": 2,
            "hard": 3
        }
        score += diff_points[difficulty]
        hints_used = data.get("hints_used", 0)
        score *= 0.9**hints_used
        rating = get_user_rating(user_id)
        set_user_rating(user_id, rating + score)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оценить", callback_data="rate")],
            [InlineKeyboardButton(text="Получить новую головоломку", callback_data="new_puzzle")],
        ])
        await message.answer(comment, reply_markup=keyboard)
        await state.clear()  # Завершаем задачу
    else:
        # Уменьшаем количество попыток
        attempts_left -= 1
        score -= 0.5
        state.update_data(score = score)
        
        if attempts_left > 0:
            await state.update_data(attempts_left=attempts_left)
            await message.answer(f"{comment}.\n\nОсталось попыток: {attempts_left}. Попробуйте снова.")
        else:
            correct_answer = data.get("correct_answer")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оценить", callback_data="rate")],
                [InlineKeyboardButton(text="Получить новую головоломку", callback_data="new_puzzle")],
            ])
            await message.answer(f"Вы исчерпали все попытки! Задача отменена.\n\nПравильный ответ: {correct_answer}", reply_markup=keyboard)
            await state.clear()  # Завершаем задачу


# Обработчик для кнопки "Получить подсказку"
@router.callback_query(lambda c: c.data == "hint")
async def handle_hint(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != PuzzleState.solving_puzzle.state:
        await callback_query.message.answer("Прежде чем получить подсказку выберите задачу")
        await callback_query.answer()
        return
    data = await state.get_data()
    puzzle_text = data.get("current_puzzle")
    hints_used = data.get("hints_used", 0)
    
    user_id = callback_query.from_user.id

    if hints_used >= 3:
        await callback_query.message.answer("Вы уже использовали все доступные подсказки для этой головоломки.")
        await callback_query.answer()
        return
    
    hints_used += 1
    await state.update_data(hints_used=hints_used)
    
    # Генерация подсказки (в данном случае для примера, можно дополнить логику)
    hint = generate_hint(user_id, puzzle_text)

    await callback_query.message.answer(f"{hint}")
    await callback_query.answer()


# Обработчик для кнопки "Отказаться"
@router.callback_query(lambda c: c.data == "cancel")
async def handle_cancel(callback_query: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != PuzzleState.solving_puzzle.state:
        await callback_query.message.answer("Чтобы отказаться от задачи, сначала нужно ее начать")
        await callback_query.answer()
        return
    # Отменяем задачу и возвращаем в исходное состояние
    data = await state.get_data()
    correct_answer = data.get("correct_answer")
    user_id = callback_query.from_user.id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оценить", callback_data="rate")],
        [InlineKeyboardButton(text="Получить новую головоломку", callback_data="new_puzzle")],
    ])
    
    await callback_query.message.answer(f"Вы отказались от задачи.\n\nПравильный ответ: {correct_answer}", reply_markup=keyboard)
    clear_user_context(user_id)
    await state.clear()
    await callback_query.answer()


@router.callback_query(lambda c: c.data == "rate")
async def handle_rate(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Пожалуйста, напишите ваш отзыв о задаче. Например, что вам понравилось или что можно улучшить.")
    await state.set_state(PuzzleState.writing_feedback)
    await callback_query.answer()
    

@router.message(PuzzleState.writing_feedback)
async def handle_feedback(message: types.Message, state: FSMContext):
    feedback = message.text
    user_id = message.from_user.id

    add_log(user_id, feedback)

    await message.answer("Спасибо за ваш отзыв! Мы ценим ваше мнение.")
    await state.clear()


@router.message()
async def handle_unrecognized_message(message: types.Message):
    keyboard = get_main_menu_keyboard()
    commands_text = (
        "Я не понимаю этот запрос. Используйте кнопки на панели снизу"
    )
    await message.reply(commands_text, reply_markup=keyboard)
    

async def my_cron_task():
    # Получаем список всех пользователей из базы данных
    users = get_all_users()  # Эта функция должна вернуть список user_id (например, [12345, 67890])
    
    # Сообщение, которое будет отправлено пользователям
    message_text = (
        "Доброе утро! 🌞\n"
        "Готовы начать день с небольшой головоломки? 🔍\n\n"
        "Нажмите на кнопку ниже, чтобы получить новую задачу:"
    )
    
    # Клавиатура с кнопкой для получения новой головоломки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Получить задачу", callback_data="new_puzzle")],
    ])
    
    # Отправляем сообщение каждому пользователю
    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=message_text, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


# Основная функция запуска
async def main():
    scheduler = AsyncIOScheduler(timezone='Europe/Moscow')
    job = scheduler.add_job(my_cron_task, 'cron', hour=10, minute=0)
    scheduler.start()
    dp.message.outer_middleware(CheckRegisterMiddleware())
    dp.include_router(router)
    initialize_database()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
