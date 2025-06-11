import json
import os
import re
import sys  # <-- обязательно нужен для sys.exit
import logging
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import threading
from flask import Flask
import threading
from flask import Flask
import os
from telegram.ext import ApplicationBuilder, MessageHandler, filters
# 🔐 Защита от повторного запуска
logging.info("Бот запускается...")  # это будет выведено только при первом запуске
ADMIN_CHAT_ID = 844673891  # Твой chat_id

if "RUNNING" in os.environ:
    logging.error("Похоже, бот уже работает. Завершаем процесс.")
    sys.exit(1)
os.environ["RUNNING"] = "true"

# ⚙️ Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 📉 Отключаем лишние логи
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# 🔑 Конфиги
TOKEN = "7604409638:AAGejgwIDKbw0NUu0QzOV43WRqK-dRb7Rlw"
BALANCE_FILE = 'balances.json'
ADMIN_USERNAME = "hto_i_taki"  # без @

# ... дальше твой код



CURRENCIES = {
    "печеньки": "🍪",
    "трилистники": "☘️",
    "четырёхлистники": "🍀"
}
LOTTERY_FILE = 'lottery.json'
# === Ваш обработчик сообщений ===


# === Заглушка HTTP-сервер для Render ===
def start_dummy_server():
    app = Flask(__name__)

    @app.route('/')
    def index():
        return "Бот работает!"

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# === Запуск бота ===
def start_bot():

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Бот запущен...")
    app.run_polling()


LEVELS_PRICE_FILE = 'levels_price.json'

from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from telegram.ext import JobQueue
import datetime

def load_levels_price():
    if not os.path.exists(LEVELS_PRICE_FILE):
        # Если файла нет — создадим дефолтные цены (10 для каждого уровня с 2 по 10)
        default_prices = {str(i): 10 for i in range(2, 11)}
        save_levels_price(default_prices)
        return default_prices
    with open(LEVELS_PRICE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)




def save_levels_price(data):
    with open(LEVELS_PRICE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
async def handle_level_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    balances = load_balances()
    user_balances = balances.get(username)

    if user_balances is None:
        await update.message.reply_text("Сначала заработайте печеньки, чтобы повысить уровень.")
        return

    current_level = user_balances.get("уровень", 1)
    if current_level >= 10:
        await update.message.reply_text("Вы уже достигли максимального уровня!")
        return

    levels_price = load_levels_price()
    next_level = str(current_level + 1)
    price = levels_price.get(next_level)

    if price is None:
        await update.message.reply_text("Не могу определить цену повышения уровня.")
        return

    current_cookies = user_balances.get("печеньки", 0)

    if current_cookies < price:
        await update.message.reply_text(f"Для повышения до уровня {next_level} нужно {price} печенек")
        return

    # Отнимаем печеньки и повышаем уровень
    user_balances["печеньки"] = current_cookies - price
    user_balances["уровень"] = current_level + 1
    balances[username] = user_balances
    save_balances(balances)

    await update.message.reply_text(f"Поздравляю! Вы повысили уровень до {next_level} и потратили {price} печенек.")
async def handle_update_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        await update.message.reply_text("Команда доступна только администратору.")
        return

    text = update.message.text.strip()
    # Ожидаем формат: "новые цены 10/10/10/10/10/10/10/10/10"
    parts = text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text("Неверный формат. Используйте: новые цены 10/10/10/10/10/10/10/10/10")
        return

    prices_str = parts[2]
    prices_list = prices_str.split('/')
    if len(prices_list) != 9:
        await update.message.reply_text("Должно быть ровно 9 цен для уровней 2-10.")
        return

    try:
        prices = [int(p) for p in prices_list]
    except ValueError:
        await update.message.reply_text("Все цены должны быть целыми числами.")
        return

    new_prices = {str(level): price for level, price in zip(range(2, 11), prices)}
    save_levels_price(new_prices)

    await update.message.reply_text(f"Цены успешно обновлены: {prices_str}")
lottery_lock = threading.Lock()

def save_lottery(data, allow_empty=False):
    if not isinstance(data, dict):
        raise ValueError("save_lottery: данные должны быть словарём.")

    if not allow_empty and (
        len(data) == 0 or all(rng[1] < rng[0] for rng in data.values())
    ):
        logging.warning("Попытка сохранить пустой или невалидный список билетов. Операция отменена.")
        return

    with lottery_lock:
        with open(LOTTERY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, separators=(',', ': '))



import threading
import os


file_lock = threading.Lock()

def load_balances():
    with file_lock:
        if not os.path.exists(BALANCE_FILE):
            return {}
        with open(BALANCE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

import random
import datetime
from telegram import User, Chat, Message, Update

file_lock1 = threading.Lock()

def save_balances(data):
    with file_lock1:
        with open(BALANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


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
    user_balances = balances.get(username)

    if user_balances is None:
        # Инициализируем нового игрока с уровнем 1 и нулём по валютам
        user_balances = {"уровень": 1}
        user_balances.update({curr: 0 for curr in CURRENCIES})
        balances[username] = user_balances
        save_balances(balances)  # сохраняем в файл

    level = user_balances.get("уровень", 1)

    lines = [f"Милашка {username}, вот твой балансик:",
             f"Уровень: {level}"]

    for curr, emoji in CURRENCIES.items():
        amount = user_balances.get(curr, 0)
        lines.append(f"{amount} {curr} {emoji}")


    # 🎟 Добавим количество билетов из лотереи
    lottery = safe_load_lottery()
    ticket_range = lottery.get(username)
    if ticket_range and isinstance(ticket_range, list) and len(ticket_range) == 2:
        ticket_count = ticket_range[1] - ticket_range[0] + 1
        if ticket_count > 0:
            lines.append(f"{ticket_count} лотерейных билетов 🎟️ ")
    lines.append(f"Ресурсы:")
    for resource_short, resource_name in RESOURCES.items():
        index = list(RESOURCES.keys()).index(resource_short)
        amount = resources[index]
        lines.append(f"  {amount} {resource_name} ({resource_short})")
    await update.message.reply_text("\n".join(lines))


def can_farm_today(last_farm_str: str) -> bool:
    """Проверяет, можно ли фармить сегодня, сравнивая даты"""
    if not last_farm_str:
        return True
    try:
        last_farm = datetime.strptime(last_farm_str, "%H:%M %d-%m-%Y")
    except Exception:
        return True  # Если формат не совпал, разрешаем фарм

    now = datetime.now()
    return now.date() > last_farm.date()
from datetime import datetime

async def handle_want_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    balances = load_balances()
    user_balances = balances.get(username)

    if user_balances is None:
        # Если юзер новый, инициализируем
        user_balances = {"уровень": 1}
        user_balances.update({curr: 0 for curr in CURRENCIES})
        balances[username] = user_balances

    # Проверяем, когда последний фарм
    last_farm_str = user_balances.get("последний фарм", "")
    if not can_farm_today(last_farm_str):
        await update.message.reply_text("Вы уже получали печеньки сегодня. Попробуйте завтра!")
        return

    level = user_balances.get("уровень", 1)
    cookies = get_cookies_by_level(level)

    # Добавляем печеньки в баланс
    user_balances["печеньки"] = user_balances.get("печеньки", 0) + cookies

    # Обновляем время последнего фарма
    user_balances["последний фарм"] = datetime.now().strftime("%H:%M %d-%m-%Y")

    # Сохраняем обновления
    balances[username] = user_balances
    save_balances(balances)

    # Логируем
    log_transaction({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "хочу печеньки",
        "to": username,
        "currency": "печеньки",
        "amount": cookies
    })

    await update.message.reply_text(f"Вы получили {cookies} 🍪 печенек! Ваш уровень: {level}")


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
    log_transaction({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "дать",
        "from": sender,
        "to": recipient,
        "currency": currency,
        "amount": amount
    })
    if random.randint(1,100)<40:
        await msg.reply_text(
            f"{sender} перевёл {amount} {currency} {CURRENCIES[currency]} {recipient}. Промокод KODE365\n"

        )
    else:
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
    log_transaction({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "дар",
        "from": "Администрация",
        "to": recipient,
        "currency": currency,
        "amount": amount
    })
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
    log_transaction({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "отнять",
        "from": "Администрация",
        "to": recipient,
        "currency": currency,
        "amount": amount
    })
    await msg.reply_text(f"{recipient} лишился {amount} {currency} {CURRENCIES[currency]}")


async def handle_save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.from_user and msg.from_user.username != ADMIN_USERNAME:
        return

    admin_chat_id = 844673891  # твой id в Telegram

    try:
        # Отправляем содержимое BALANCE_FILE
        with open(BALANCE_FILE, 'r', encoding='utf-8') as f:
            balance_content = f.read()

        if len(balance_content) <= 4000:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"📂 *Содержимое {BALANCE_FILE}*\n```json\n{balance_content}\n```",
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_document(
                chat_id=admin_chat_id,
                document=open(BALANCE_FILE, 'rb')
            )

        # Отправляем содержимое levels_price.json
        with open('levels_price.json', 'r', encoding='utf-8') as f:
            levels_content = f.read()

        if len(levels_content) <= 4000:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"📊 *Цены уровней (levels_price.json)*\n```json\n{levels_content}\n```",
                parse_mode="Markdown"
            )
        else:
            await context.bot.send_document(
                chat_id=admin_chat_id,
                document=open('levels_price.json', 'rb')
            )

        # Теперь отправляем содержимое лотереи (с безопасной загрузкой)
        lottery = safe_load_lottery()
        if not lottery:
            await context.bot.send_message(chat_id=admin_chat_id, text="🎟️ Файл с билетами пуст.")
        else:
            json_text = json.dumps(lottery, ensure_ascii=False, indent=2, separators=(',', ': '))


            if len(json_text) <= 4000:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🎟️ *Содержимое лотереи*\n```json\n{json_text}\n```",
                    parse_mode="Markdown"
                )
            else:
                temp_path = "lottery.json"
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(json_text)
                await context.bot.send_document(chat_id=admin_chat_id, document=open(temp_path, "rb"))
                os.remove(temp_path)

    except Exception as e:
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=f"❌ Ошибка при чтении файлов: {e}"
        )




async def handle_clear_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_username_from_message(update.message) != f"@{ADMIN_USERNAME}":
        await update.message.reply_text("Эта команда только для админа.")
        return

    save_lottery({}, allow_empty=True)
    await update.message.reply_text("Билеты очищены.")


async def handle_average_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_balances()
    if not balances:
        await update.message.reply_text("Нет данных по балансу.")
        return

    excluded_users = {"@hto_i_taki", "@Shittttt", "@zZardexe", "@insanemaloy"}

    total = 0
    count = 0
    for user, user_balances in balances.items():
        if user in excluded_users:
            continue
        cookies = user_balances.get("печеньки", 0)
        total += cookies
        count += 1

    if count == 0:
        await update.message.reply_text("Нет пользователей с печеньками (после исключения).")
        return

    average = total / count
    await update.message.reply_text(f"Среднее количество печенек (без админов): {average:.2f} 🍪")
async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    is_admin = (username == f"@{ADMIN_USERNAME}")



    # Для обычных пользователей покажем только команды без пометки (админ)
    if not is_admin:
        filtered_commands = {cmd: desc for cmd, desc in commands_common.items() if "(админ)" not in desc}
    else:
        filtered_commands = commands_common

    lines = ["Доступные команды:"]
    for cmd, desc in filtered_commands.items():
        lines.append(f"{cmd} — {desc}")

    await update.message.reply_text("\n".join(lines))


def get_cookies_by_level(level: int) -> int:
    # Определяем диапазон и веса вероятностей по уровню
    # Формат: (min, max, [вес1, вес2, ...])

    cfg = level_config.get(level, (0, 1, [0.5, 0.5]))  # дефолт для уровней > 10 или <1
    min_val, max_val, weights = cfg

    # Формируем список вариантов
    values = list(range(min_val, max_val + 1))

    # Выбираем с учётом весов
    cookies = random.choices(values, weights=weights, k=1)[0]
    return cookies

excluded_users = {"@hto_i_taki", "@Shittttt", "@zZardexe", "@insanemaloy"}  # админы
excluded_users_Admin = {"@hto_i_taki"}  # исключить полностью

async def handle_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balances = load_balances()

    def clean_username(name):
        return name.lstrip('@')

    # Пользователи без excluded_users_Admin
    balances_no_admin_global = {
        user: data for user, data in balances.items()
        if user not in excluded_users_Admin
    }

    # Пользователи без всех админов
    balances_no_admins = {
        user: data for user, data in balances.items()
        if user not in excluded_users
    }

    # Топ 5 по Печенькам (все, кроме @hto_i_taki)
    top_cookies = sorted(
        balances_no_admin_global.items(),
        key=lambda x: x[1].get("печеньки", 0),
        reverse=True
    )[:5]

    # Топ 5 по Печенькам без админов
    top_cookies_no_admins = sorted(
        balances_no_admins.items(),
        key=lambda x: x[1].get("печеньки", 0),
        reverse=True
    )[:5]

    # Топ 5 по Уровням (все, кроме @hto_i_taki)
    top_levels = sorted(
        balances_no_admin_global.items(),
        key=lambda x: x[1].get("уровень", 1),
        reverse=True
    )[:5]

    # Топ 5 по Уровням без админов
    top_levels_no_admins = sorted(
        balances_no_admins.items(),
        key=lambda x: x[1].get("уровень", 1),
        reverse=True
    )[:5]

    lines = ["🏆 Топ 5 по Печенькам:"]
    for i, (user, data) in enumerate(top_cookies, 1):
        lines.append(f"{i}. {clean_username(user)} — {data.get('печеньки', 0)} 🍪")

    lines.append("\n🚫 Топ 5 по Печенькам без админов:")
    for i, (user, data) in enumerate(top_cookies_no_admins, 1):
        lines.append(f"{i}. {clean_username(user)} — {data.get('печеньки', 0)} 🍪")

    lines.append("\n🎖️ Топ 5 по Уровням:")
    for i, (user, data) in enumerate(top_levels, 1):
        lines.append(f"{i}. {clean_username(user)} — уровень {data.get('уровень', 1)}")

    lines.append("\n🎖️ Топ 5 по Уровням без админов:")
    for i, (user, data) in enumerate(top_levels_no_admins, 1):
        lines.append(f"{i}. {clean_username(user)} — уровень {data.get('уровень', 1)}")

    await update.message.reply_text("\n".join(lines))

import random  # добавьте в начало файла, если ещё не импортировали
from telegram import User, Chat, Message  # тоже добавьте в импорты


ADMIN_CHAT_ID = 844673891  # ID администратора

async def handle_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("Команда доступна только администратору.")
        return

    text = update.message.text.strip()
    args = text.split()

    try:
        with open(TRANSACTION_LOG_FILE, "r", encoding="utf-8") as f:
            transactions = json.load(f)
    except FileNotFoundError:
        await update.message.reply_text("Архив пуст.")
        return

    if not transactions:
        await update.message.reply_text("Архив пуст..")
        return

    # Определяем сколько транзакций показывать
    if len(args) == 1:
        count = 5  # по умолчанию

    elif len(args) == 2:
        if args[1].lower() == "все":
            count = len(transactions)
        elif args[1].isdigit():
            count = int(args[1])
        else:
            await update.message.reply_text("Неверный формат. Используй: архив [все|число]")
            return
    else:
        await update.message.reply_text("Неверный формат. Используй: архив [все|число]")
        return

    # Показываем последние count записей
    to_show = transactions[-count:]
    lines = []
    for tx in reversed(to_show):  # показываем от новых к старым
        time = tx.get("timestamp", "")
        ttype = tx.get("type", "")
        frm = tx.get("from", "")
        to = tx.get("to", "")
        curr = tx.get("currency", "")
        amt = tx.get("amount", "")
        line = f"[{time}] {ttype}: {frm} ➝ {to}, {amt} {curr}"
        lines.append(line)

    message = "\n".join(lines)
    if len(message) > 4096:  # Ограничение Telegram
        for i in range(0, len(message), 4096):
            await update.message.reply_text(message[i:i + 4096])
    else:
        await update.message.reply_text(message)

async def handle_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 <b>WardShield Server Info</b>\n\n"
        "💬 <b>Telegram чат:</b> <a href='https://t.me/+aLhslgqdoz1kYjky'>вступить</a>\n"
        "🌐 <b>IP:</b> <code>WardShield_3.aternos.me</code>\n"
        "🎮 <b>Версия Minecraft:</b> 1.21.1",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

def safe_load_lottery():
    with lottery_lock:
        try:
            with open(LOTTERY_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}



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
        await msg.reply_text(f"Недостаточно печенек.")
        return

    # Вычитаем печеньки
    balances.setdefault(username, {}).setdefault("печеньки", 0)
    balances[username]["печеньки"] -= count
    save_balances(balances)

    # Загрузка текущих билетов
    lottery =safe_load_lottery()
    ordered = list(lottery.items())

    # Найдём текущего пользователя и его количество билетов
    current_index = next((i for i, (user, _) in enumerate(ordered) if user == username), None)
    previous_tickets = 0

    if current_index is not None:
        prev_range = ordered[current_index][1]
        previous_tickets = prev_range[1] - prev_range[0] + 1
        ordered.pop(current_index)
    else:
        previous_tickets = 0

    total_tickets = previous_tickets + count
    # Добавим пользователя в конец
    ordered.append((username, [0, 0]))  # добавим позже, но без риска

    # Пересчёт
    current_number = 1
    for i, (user, rng) in enumerate(ordered):
        if user == username:
            new_range = [current_number, current_number + total_tickets - 1]
        else:
            ticket_count = rng[1] - rng[0] + 1
            new_range = [current_number, current_number + ticket_count - 1]
        ordered[i] = (user, new_range)
        current_number = new_range[1] + 1

    updated_lottery = {user: rng for user, rng in ordered}
    save_lottery(updated_lottery)
    log_transaction({
        "timestamp": datetime.utcnow().isoformat(),
        "type": "Лото-Печенько-Рея",
        "from": username,
        "to": "лотерея",
        "currency": "печеньки",
        "amount": count
    })

    user_range = updated_lottery[username]
    await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪")

async def handle_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(UPDATE_LOG.strip())


import os
import json

async def handle_show_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    if username != f"@{ADMIN_USERNAME}":
        await update.message.reply_text("Эта команда доступна только админу.")
        return

    lottery =safe_load_lottery()
    if not lottery:
        await update.message.reply_text("Файл с билетами пуст.")
        return

    json_text = json.dumps(lottery, ensure_ascii=False, indent=2, separators=(',', ': '))


    if len(json_text) > 4000:
        temp_path = "lottery.json"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(json_text)

        with open(temp_path, "rb") as doc:
            await update.message.reply_document(document=doc)

        os.remove(temp_path)
    else:
        await update.message.reply_text(
            f"Содержимое файла:\n```json\n{json_text}\n```",
            parse_mode="Markdown"
        )
RESOURCES = {
    "к": "Какао-бобы",
    "п": "Пшеница",
    "ж": "Железо",
    "а": "Алмазы",
    "з": "Золото",
    "и": "Изумруды",
    "р": "Золотая печенька"  # 🌟
}
def get_user_resources(username, balances):
    user_data = balances.get(username, {})
    resources_str = user_data.get("ресурсы", "0/0/0/0/0/0/0")
    return list(map(int, resources_str.split('/')))
def update_user_resources(username, balances, resources):
    resources_str = '/'.join(map(str, resources))
    if username not in balances:
        balances[username] = {}
    balances[username]["ресурсы"] = resources_str
    save_balances(balances)
async def handle_give_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    # Удаляем префикс "рес дать" и обрабатываем оставшуюся часть
    command = text.replace("рес дать", "").strip()
    match = re.match(r'^(\d+)\s+(\w)', command, re.IGNORECASE)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: рес дать <количество> <ресурс>")
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()

    if resource_short not in RESOURCES:
        await msg.reply_text("Неизвестный ресурс.")
        return

    resource_name = RESOURCES[resource_short]
    sender = get_username_from_message(msg)
    recipient_tag = None

    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"

    if sender == recipient:
        await msg.reply_text("Нельзя переводить себе ресурсы!")
        return

    balances = load_balances()
    sender_resources = get_user_resources(sender, balances)
    recipient_resources = get_user_resources(recipient, balances)

    resource_index = list(RESOURCES.keys()).index(resource_short)

    if sender_resources[resource_index] < amount:
        await msg.reply_text(f"У тебя недостаточно {resource_name}.")
        return

    # Списываем у отправителя
    sender_resources[resource_index] -= amount
    update_user_resources(sender, balances, sender_resources)

    # Начисляем получателю
    recipient_resources[resource_index] += amount
    update_user_resources(recipient, balances, recipient_resources)

    await msg.reply_text(f"{sender} перевёл {amount} {resource_name} {recipient}.")
async def handle_give_admin_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()

    # Удаляем префикс "рес дар" и обрабатываем оставшуюся часть
    command = text.replace("рес дар", "").strip()
    match = re.match(r'^(\d+)\s+(\w)(?:\s+@(\w+))?', command, re.IGNORECASE)
    if not match:
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()
    recipient_tag = match.group(3)

    if resource_short not in RESOURCES:
        await msg.reply_text("Неизвестный ресурс.")
        return

    resource_name = RESOURCES[resource_short]

    if not recipient_tag and msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()
    recipient_resources = get_user_resources(recipient, balances)

    resource_index = list(RESOURCES.keys()).index(resource_short)

    recipient_resources[resource_index] += amount
    update_user_resources(recipient, balances, recipient_resources)

    await msg.reply_text(f"{recipient} получил {amount} {resource_name} от администрации.")
async def handle_take_admin_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()

    # Удаляем префикс "рес отнять" и обрабатываем оставшуюся часть
    command = text.replace("рес отнять", "").strip()
    match = re.match(r'^(\d+)\s+(\w)(?:\s+@(\w+))?', command, re.IGNORECASE)
    if not match:
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()
    recipient_tag = match.group(3)

    if resource_short not in RESOURCES:
        await msg.reply_text("Неизвестный ресурс.")
        return

    resource_name = RESOURCES[resource_short]

    if not recipient_tag and msg.reply_to_message:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()
    recipient_resources = get_user_resources(recipient, balances)

    resource_index = list(RESOURCES.keys()).index(resource_short)

    recipient_resources[resource_index] = max(0, recipient_resources[resource_index] - amount)
    update_user_resources(recipient, balances, recipient_resources)

    await msg.reply_text(f"{recipient} лишился {amount} {resource_name}.")
async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lower_text = text.lower()
    username = get_username_from_message(update.message)

    async def maybe_save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):

            fake_user = User(id=844673891, first_name="Admin", is_bot=False, username=ADMIN_USERNAME)
            fake_chat = Chat(id=844673891, type="private")
            fake_message = Message(message_id=0, date=update.message.date, chat=fake_chat, from_user=fake_user,
                                   text="сохранение")
            fake_update = Update(update_id=0, message=fake_message)
            await handle_save_admin(fake_update, context)
    # Ваши условия остаются без изменений:
    if lower_text.startswith("баланс"):
        await handle_balance(update, context)
    elif lower_text.startswith("дать"):
        await handle_give(update, context)
        if random.random() < 0.25:
            await maybe_save_admin(update, context)
    elif lower_text.startswith("дар"):
        await handle_give_admin(update, context)
        if random.random() < 0.25:
            await maybe_save_admin(update, context)
    elif lower_text.startswith("отнять"):
        await handle_take_admin(update, context)
        if random.random() < 0.4:
            await maybe_save_admin(update, context)
    elif lower_text.startswith("сохранение"):
        await handle_save_admin(update, context)
    elif re.match(r'^N\s+\d+$', text, re.IGNORECASE):
        await handle_lottery_purchase(update, context)
    elif lower_text.startswith("показать"):
        await handle_show_lottery(update, context)
    elif lower_text.startswith("очистить"):
        await handle_clear_lottery(update, context)
    elif lower_text.startswith("среднее"):
        await handle_average_cookies(update, context)
    elif lower_text == "хочу печеньки":
        await handle_want_cookies(update, context)
        if random.random() < 0.2:
            await maybe_save_admin(update, context)
    elif lower_text == "повысить уровень":
        await handle_level_up(update, context)
        if random.random() < 0.25:
            await maybe_save_admin(update, context)
    elif lower_text.startswith("новые цены") and username == f"@{ADMIN_USERNAME}":
        await handle_update_prices(update, context)
    elif lower_text == "команды":
        await handle_commands(update, context)
    elif lower_text == "топ" or lower_text == "топчик":
        await handle_top(update, context)
    elif lower_text == "уровень":
        await handle_level_info(update, context)
    elif lower_text.startswith("архив"):
        await handle_transactions(update, context)
    elif any(phrase in lower_text for phrase in {"инфо", "ip", "инфа", "информация", "дайте ip", "скиньте ip", "какое ip", "какое ип"}):
        await handle_info_command(update, context)
    elif lower_text.startswith("обнова"):
        await handle_updates(update, context)
    elif lower_text == "kode365":
        await update.message.reply_text("@hto_i_taki промик нашли!")
    elif lower_text.startswith("рес дать"):
        await handle_give_resources(update, context)
    elif lower_text.startswith("рес дар"):
        await handle_give_admin_resources(update, context)
    elif lower_text.startswith("рес отнять"):
        await handle_take_admin_resources(update, context)
commands_common = {
    "рес дать <число> <ресурс>": "Передать ресурс другому игроку",
    "рес дар <число> <ресурс>": "Передать ресурс от администратора (админ)",
    "рес отнять <число> <ресурс>": "Отнять ресурс у игрока (админ)",
    "обнова": "Показать список обновлений",
    "баланс": "Показать текущий баланс и уровень",
    "дать <число>": "Передать печеньки другому игроку",
    "дар <число>": "Передать печеньки от администратора (админ)",
    "отнять <число>": "Отнять печеньки у игрока (админ)",
    "сохранение": "Сохранить данные (админ)",
    "показать": "Показать лотерею (админ)",
    "очистить": "Очистить лотерею (админ)",
    "среднее": "Показать среднее количество печенек у игроков",
    "хочу печеньки": "Получить печеньки случайным образом",
    "повысить уровень": "Повысить свой уровень, потратив печеньки",
    "новые цены": "Обновить цены на уровни (админ)",
    "N <число>": "Купить указанное количество лотерейных билетов",
    "топ": "Топ 5 игроков по печенькам и уровням + топ без админов",
    "уровень": "Информация о шансах и ценах для каждого уровня",
    "архив [все|число]": "Показать последние N или все транзакции (админ)"
}
UPDATE_LOG = """
📦 Последние обновления:

✅ Добавлена Пшеница, Какао-бобы, железо, золото, алмазы, изумруды ️
✅ Добавлена доп защита от отката в билетах ️
✅ Обновлена  фраза  в балансе ️
✅ Исправлена команда "N <число>" — покупка билетов 🎟️
✅ Команда "баланс" теперь показывает количество билетов
✅ Исправлена ошибка с покупкой 1 билета
🛠 Оптимизирована функция сохранения лотереи
"""



async def handle_level_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Загружаем цены
    try:
        with open("levels_price.json", "r", encoding="utf-8") as f:
            prices = json.load(f)
    except FileNotFoundError:
        prices = {}

    lines = ["📊 *Информация об уровнях*",
             "Уровень увеличивает фарм печенек и открывает новые возможности.\n"]

    for level in range(1, 11):
        min_amt, max_amt, chances = level_config[level]
        chance_str = "/".join(f"{round(p * 100)}" for p in chances)
        price = prices.get(str(level), "🚫" if level == 1 else "неизвестно")

        lines.append(
            f"*{level} уровень*: {min_amt}–{max_amt} 🍪 в день — шанс: {chance_str} — цена: {price}"
        )

    lines.append("\n📉 *Откуп от поражения*")
    lines.append("Уровень понижает цену откупа в 2 раза, если достигнут нужный уровень.\n")
    lines.append("*Формат:* `(Ступень — Этап) : Нужный уровень`")
    lines.append("""
    📌 *Подготовительный Этап*
    - 1 ступень : 2 ур
    - 2 ступень : 4 ур
    - 3 ступень : 6 ур
    - Финал ПЭ : 8 ур
    
    📌 *Основная часть*
    - Первый Этап : 10 ур
    - Второй Этап : 12 ур
    - Третий Этап : 14 ур
    - Финал : 🚫 откуп не доступен
    """)

    lines.append("📎 *Пример 1*:\nФинал Подготовительного Этапа. Базовая цена откупа — 150 🍪.\n"
                 "Если у вас *8 уровень*, цена будет в 2 раза ниже: *75 🍪*.")

    lines.append("📎 *Пример 2*:\nЕсли у вас *7 уровень* в том же этапе, то каждый уровень снижает цену на *5 🍪*:\n"
                 "`150 - 7×5 = 115 🍪`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

TRANSACTION_LOG_FILE = "transactions.json"

def log_transaction(entry: dict):
    try:
        with open(TRANSACTION_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    data.append(entry)

    with open(TRANSACTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

level_config = {
        1: (0, 2, [0.49, 0.5, 0.01]),
        2: (0, 2, [0.19, 0.8, 0.01]),
        3: (0, 2, [0.19, 0.4, 0.41]),
        4: (0, 4, [0.09, 0.25, 0.25, 0.4, 0.01]),
        5: (1, 4, [0.19, 0.3, 0.5,0.01]),
        6: (1, 4, [0.05, 0.4, 0.4, 0.15]),
        7: (2, 4, [0.4, 0.4,0.2]),
        8: (2, 5, [0.2, 0.4,0.3,0.1]),
        9: (2, 5, [0.1, 0.3,0.4,0.2]),
        10: (2, 6, [0.1, 0.2, 0.5, 0.15, 0.05]),
    }
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Бот запущен...")
    app.run_polling()
