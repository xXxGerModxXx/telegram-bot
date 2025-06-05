import json
import os
import re
import logging
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Отключаем логи INFO для httpx (Telegram Bot API клиент)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

TOKEN = "7604409638:AAFRrmzPflnsGj_a7q2fMd99w3x_GuNJ78c"
BALANCE_FILE = 'balances.json'
ADMIN_USERNAME = "hto_i_taki"  # без @

# ... дальше твой код


CURRENCIES = {
    "печеньки": "🍪",
    "трилистники": "☘️",
    "четырёхлистники": "🍀"
}
LOTTERY_FILE = 'lottery.json'

def load_lottery():
    if not os.path.exists(LOTTERY_FILE):
        return {}
    with open(LOTTERY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_lottery(data):
    with open(LOTTERY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_balances():
    if not os.path.exists(BALANCE_FILE):
        return {}
    with open(BALANCE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_balances(balances):
    with open(BALANCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

def get_username_from_message(msg: Message) -> str:
    return f"@{msg.from_user.username}" if msg.from_user.username else f"id{msg.from_user.id}"

def get_currency_from_text(text: str) -> str:
    # Определяем валюту по ключевому слову в тексте, если не указано - печеньки
    for curr in CURRENCIES.keys():
        if curr in text:
            return curr
    return "печеньки"

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    balances = load_balances()
    user_balances = balances.get(username, {})
    if not user_balances:
        user_balances = {curr: 0 for curr in CURRENCIES}
    # Формируем ответ с балансом по всем валютам
    lines = [f"{username}, твой баланс:"]
    for curr, emoji in CURRENCIES.items():
        amount = user_balances.get(curr, 0)
        lines.append(f"{amount} {curr} {emoji}")
    await update.message.reply_text("\n".join(lines))

async def handle_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    # Регулярка теперь ищет: "дать N [название валюты]"
    match = re.match(r'^дать\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?', text, re.IGNORECASE)
    if not match:
        return

    amount = int(match.group(1))
    currency_text = match.group(2)

    # Приводим к правильному ключу валюты
    if currency_text:
        currency_text = currency_text.lower()
        # нормализуем варианты
        if currency_text in ("трилистника", "трилистники"):
            currency = "трилистники"
        elif currency_text in ("четырёхлистника", "четырёхлистники"):
            currency = "четырёхлистники"
        else:
            currency = "печеньки"
    else:
        currency = "печеньки"

    recipient_tag = None
    # Ищем получателя: либо через @, либо в ответе на сообщение
    # Пример: "дать 10 трилистника @username"
    recipient_match = re.search(r'@(\w+)', text)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    sender = get_username_from_message(msg)
    recipient = f"@{recipient_tag}"

    if sender == recipient:
        await msg.reply_text("Нельзя переводить себе валюту!")
        return

    balances = load_balances()
    sender_balances = balances.get(sender, {curr: 0 for curr in CURRENCIES})

    if sender_balances.get(currency, 0) < amount:
        await msg.reply_text(f"У тебя недостаточно {currency}.")
        return

    # Списываем и начисляем
    sender_balances[currency] = sender_balances.get(currency, 0) - amount
    balances[sender] = sender_balances

    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    recipient_balances[currency] = recipient_balances.get(currency, 0) + amount
    balances[recipient] = recipient_balances

    save_balances(balances)

    await msg.reply_text(
        f"{sender} перевёл {amount} {currency} {CURRENCIES[currency]} {recipient}.\n"

    )

async def handle_give_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    match = re.match(r'^дар\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?(?:\s+@(\w+))?', text, re.IGNORECASE)
    if not match:
        return

    amount = int(match.group(1))
    currency_text = match.group(2)
    recipient_tag = match.group(3)

    if currency_text:
        currency_text = currency_text.lower()
        if currency_text in ("трилистника", "трилистники"):
            currency = "трилистники"
        elif currency_text in ("четырёхлистника", "четырёхлистники"):
            currency = "четырёхлистники"
        else:
            currency = "печеньки"
    else:
        currency = "печеньки"

    if not recipient_tag and msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    recipient_balances[currency] = recipient_balances.get(currency, 0) + amount
    balances[recipient] = recipient_balances

    save_balances(balances)
    await msg.reply_text(f"{recipient} получил {amount} {currency} {CURRENCIES[currency]} от администрации")

async def handle_take_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    match = re.match(r'^отнять\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?(?:\s+@(\w+))?', text, re.IGNORECASE)
    if not match:
        return

    amount = int(match.group(1))
    currency_text = match.group(2)
    recipient_tag = match.group(3)

    if currency_text:
        currency_text = currency_text.lower()
        if currency_text in ("трилистника", "трилистники"):
            currency = "трилистники"
        elif currency_text in ("четырёхлистника", "четырёхлистники"):
            currency = "четырёхлистники"
        else:
            currency = "печеньки"
    else:
        currency = "печеньки"

    if not recipient_tag and msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    current = recipient_balances.get(currency, 0)
    recipient_balances[currency] = max(0, current - amount)
    balances[recipient] = recipient_balances

    save_balances(balances)
    await msg.reply_text(f"{recipient} лишился {amount} {currency} {CURRENCIES[currency]}")
async def handle_save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    try:
        with open(BALANCE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            # Telegram ограничивает 4096 символов на сообщение
            if len(content) <= 4096:
                await msg.reply_text(f"```json\n{content}\n```", parse_mode="Markdown")
            else:
                # Если слишком длинный — отправим как файл
                await msg.reply_document(document=open(BALANCE_FILE, 'rb'))
    except Exception as e:
        await msg.reply_text(f"Ошибка при чтении баланса: {e}")
async def handle_lottery_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    username = get_username_from_message(msg)
    text = msg.text.strip()

    match = re.match(r'^N\s+(\d+)$', text, re.IGNORECASE)
    if not match:
        return

    count = int(match.group(1))
    if count <= 0:
        await msg.reply_text("Количество билетов должно быть больше нуля.")
        return

    balances = load_balances()
    user_bal = balances.get(username, {}).get("печеньки", 0)

    if user_bal < count:
        await msg.reply_text(f"Недостаточно печенек. У тебя {user_bal}, нужно {count}.")
        return

    # Вычитаем печеньки
    balances.setdefault(username, {}).setdefault("печеньки", 0)
    balances[username]["печеньки"] -= count
    save_balances(balances)

    # Загрузка текущих билетов
    lottery = load_lottery()

    # Преобразуем в список, сохраняем порядок
    ordered = list(lottery.items())

    # Найдём текущую позицию пользователя (если есть)
    current_index = next((i for i, (user, _) in enumerate(ordered) if user == username), None)

    if current_index is not None:
        # Если пользователь уже есть — увеличиваем его билеты
        old_range = ordered[current_index][1]
        new_count = (old_range[1] - old_range[0] + 1) + count
        ordered[current_index] = (username, [0, 0])  # временно нули, позже пересчитаем
    else:
        # Новый пользователь
        ordered.append((username, [0, 0]))
        current_index = len(ordered) - 1

    # Перерасчёт диапазонов заново — слева направо
    current_number = 1
    for i, (user, rng) in enumerate(ordered):
        if i == current_index:
            ticket_count = count if rng == [0, 0] else (rng[1] - rng[0] + 1)
            new_range = [current_number, current_number + ticket_count - 1]
            ordered[i] = (username, new_range)
        else:
            ticket_count = rng[1] - rng[0] + 1
            new_range = [current_number, current_number + ticket_count - 1]
            ordered[i] = (user, new_range)

        current_number = new_range[1] + 1

    # Сохраняем обратно в словарь
    updated_lottery = {user: rng for user, rng in ordered}
    save_lottery(updated_lottery)

    user_range = updated_lottery[username]
    await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪")


async def handle_show_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from pprint import pformat  # для более читаемого вывода

    username = get_username_from_message(update.message)
    if username != f"@{ADMIN_USERNAME}":
        await update.message.reply_text("Эта команда доступна только админу.")
        return

    lottery = load_lottery()
    if not lottery:
        await update.message.reply_text("Файл с билетами пуст.")
        return

    raw_text = pformat(lottery, width=80)
    await update.message.reply_text(f"Содержимое файла:\n{raw_text}")

async def handle_clear_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_lottery({})
    await update.message.reply_text("Билеты очищены.")


async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lower_text = text.lower()
    username = get_username_from_message(update.message)

    if lower_text.startswith("баланс"):
        await handle_balance(update, context)
    elif lower_text.startswith("дать"):
        await handle_give(update, context)
    elif lower_text.startswith("дар"):
        await handle_give_admin(update, context)
    elif lower_text.startswith("отнять"):
        await handle_take_admin(update, context)
    elif lower_text.startswith("сохранение"):
        await handle_save_admin(update, context)
    elif re.match(r'^N\s+\d+$', text, re.IGNORECASE):
        await handle_lottery_purchase(update, context)
    elif lower_text == "показать" and update.message.from_user.username == ADMIN_USERNAME:
        await handle_show_lottery(update, context)
    elif lower_text == "очистить" and update.message.from_user.username == ADMIN_USERNAME:
        await handle_clear_lottery(update, context)


if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Бот запущен...")
    app.run_polling()
