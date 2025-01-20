from gradio_client import Client
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.llms.base import LLM
from typing import Optional, List

client = Client("Qwen/Qwen2.5-72B-Instruct")

class QwenLLM(LLM):
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        response = client.predict(prompt, api_name="/model_chat")
        return response[1][0][1]

    @property
    def _llm_type(self) -> str:
        return "qwen_llm"

llm = QwenLLM()

context_buffers = {}

def update_user_context(user_id: int, new_entry: str, max_size: int = 500):
    if user_id not in context_buffers:
        context_buffers[user_id] = []

    context_buffers[user_id].append(new_entry)

    if len(context_buffers[user_id]) > max_size:
        context_buffers[user_id].pop(0)

def get_user_context(user_id: int) -> str:
    return "\n".join(context_buffers.get(user_id, []))

def clear_user_context(user_id: int):
    if user_id in context_buffers:
        del context_buffers[user_id]


def generate_puzzle_with_user_context(user_id: int, topic: str, difficulty: str):
    context = get_user_context(user_id)

    puzzle_prompt = PromptTemplate(
        input_variables=["topic", "difficulty", "context"],
        template=(
            "Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
            "markdown в своих ответах."
            "Создай уникальную головоломку на тему '{topic}' с уровнем сложности '{difficulty}'.\n\n"
            "Контекст: {context}\n"
            "Укажи текст задачи и правильный ответ с кратким пояснением, разделив их символом $"
        )
    )

    chain = LLMChain(llm=llm, prompt=puzzle_prompt)
    prompt_result = chain.run(topic=topic, difficulty=difficulty, context=context)

    puzzle_data = prompt_result.split("$")
    puzzle_text = puzzle_data[0].strip()
    correct_answer = puzzle_data[1].strip() if len(puzzle_data) > 1 else "Ответ не найден."

    update_user_context(user_id, f"Новая загадка: {puzzle_text}")

    return {
        "puzzle": puzzle_text,
        "answer": correct_answer,
    }

def generate_hint(user_id: int, puzzle_text: str):
    context = get_user_context(user_id)

    hint_prompt = PromptTemplate(
        input_variables=["puzzle_text", "context"],
        template=(
            "Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
            "markdown в своих ответах."
            "Дай одну короткую подсказку для следующей головоломки:\n"
            "Головоломка: {puzzle_text}\n"
            "Контекст: {context}"
            "Не говори ответ, лишь намекни на то, как лучше решать головоломку"
        )
    )

    chain = LLMChain(llm=llm, prompt=hint_prompt)
    hint = chain.run(puzzle_text=puzzle_text, context=context).strip()

    update_user_context(user_id, f"Использована подсказка: {hint}")

    return hint


def check_answer(user_id: int, puzzle_text: str, user_answer: str):
    context = get_user_context(user_id)

    check_prompt = PromptTemplate(
        input_variables=["puzzle_text", "user_answer", "context"],
        template=(
            "Вы являетесь ассистентом, который помогает создавать и решать головоломки. Вы не должны использовать "
            "markdown в своих ответах."
            "Проверь ответ пользователя на следующую головоломку:\n"
            "Головоломка: {puzzle_text}\n"
            "Ответ пользователя: {user_answer}\n"
            "Контекст: {context}\n"
            "Сообщи, является ли ответ верным, и объясни почему. Если ответ неверный объясни почему он неверный, но не пиши правильный ответ. Если ответ однозначно верный, помимо текста поставь знак $ в самое начало."
            "Учитывай, что твой ответ будет напрямую отправлен пользователю, поэтому обращайся лично к нему"
        )
    )

    chain = LLMChain(llm=llm, prompt=check_prompt)
    ans = chain.run(puzzle_text=puzzle_text, user_answer=user_answer, context=context).strip()

    if ans.startswith("$"):
        clear_user_context(user_id)
        return [1, ans[1:].strip()]
    update_user_context(user_id, f"Был дан ответ: {user_answer}")
    return [0, ans]
