from httpx import ConnectError
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import re
import base64

class TooMany(RuntimeError):
    def __str__(self):
        return "Слишком много запросов. Сервер устал. Попробуйте позже."


class NotEthical(ValueError):
    def __str__(self):
        return "Gigachat отказался отвечать по моральным соображениям."


class NotPhoto(ValueError):
    def __str__(self):
        return "Gigachat не смог сгенерировать изображение по описанию."


def summary(text: str) -> str:
    """
    Генерирует краткое содержание текста
    """
    giga = GigaChat(
        credentials=KEY,
        verify_ssl_certs=False,
    )
    # messages = [
    #     SystemMessage(content="""Ты профессиональный суммаризатор текстов.
    #                    Сгенерируй краткое содержание на русском языке.""")
    # ]
    # messages.append(HumanMessage(content=text))
    # try:
    #     response = giga.invoke(messages)
    #     answer = response.content
    #     # Проверяем все возможные случаи отказа
    #     if ("этич" in answer.lower() or
    #             "отказываюсь" in answer.lower() or
    #             "blacklist" in str(response) or
    #             "Не люблю менять тему" in answer):
    #         raise NotEthical
    #     return answer
    # except ConnectError:
    #     raise ConnectError
    # except NotEthical:
    #     raise NotEthical
    # except Exception as e:
    #     if "TooMany" in str(e) or "429" in str(e):
    #         raise TooMany

    system_prompt = (
        """Ты профессиональный суммаризатор текстов. Твоя задача:\n
        1. Анализировать предоставленный текст\n
        2. Выделять ключевые тезисы и основные идеи\n
        3. Формировать сжатое изложение\n\n

        Жёсткие требования:
        ✓ Сохраняй исходный смысл и контекст\n
        "× Запрещено вводить информацию не из текста"""
    )

    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=system_prompt
            ),
            Messages(role=MessagesRole.USER,
                     content=text)
        ],
        # temperature=0.7,
        # max_tokens=100,
    )

    response = giga.chat(payload)
    return response.choices[0].message.content


def gen_photo(query: str, path: str = "") -> str:
    if path == "":
        path = "last_giga_image.png"
    giga = GigaChat(
        credentials=KEY,
        verify_ssl_certs=False)

    system_prompt = """Ты профессиональный генератор изображений. Твоя задача - 
        1. Анализировать полученное описание\n
        2. Создавать уникальное изображение по описанию\n

        Жёсткие правила:\n
        × Запрещено добавлять пояснения, описания или комментарии\n
        × Запрещено задавать уточняющие вопросы\n
        × Запрещено использовать разметку или форматирование\n"""

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=query)],
        # temperature=0.7,
        # max_tokens=100,
        function_call="auto",
    )

    try:
        img = giga.chat(payload)
    except ConnectError:
        raise ConnectError("что-т не работает")
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
    #print(img)
    content = img.choices[0].message.content
    #print(content)
    # print(giga.get_image(content))
    file_id = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', content)
    print(file_id)

    if file_id is None:
        raise NotPhoto
    image_data = giga.get_image(file_id.group(0))
    with open(path, "wb") as f:
        f.write(base64.b64decode(image_data.content))


def get_help(query: str) -> str:
    giga = GigaChat(
        credentials=KEY,
        verify_ssl_certs=False,
    )

    payload = Chat(messages=[
        Messages(role=MessagesRole.USER,
                 content=query)
    ],
        # temperature=0.7,
        # max_tokens=100,
    )

    response = giga.chat(payload)
    return response.choices[0].message.content
