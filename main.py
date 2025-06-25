
import sys  # <-- обязательно нужен для sys.exit
import logging
from telegram import Update

import threading
from flask import Flask
import os

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
TOKEN = "7604409638:AAHFrSALESjELw4y5aA-L3fAs8jwdQyzYuo"
BALANCE_FILE = 'обновление/balances.json'
ADMIN_USERNAME = "hto_i_taki"  # без @

# ... дальше твой код



CURRENCIES = {
    "печеньки": "🍪",
    "трилистники": "☘️",
    "четырёхлистники": "🍀"
}
LOTTERY_FILE = 'обновление/lottery.json'
# Flask-заглушка
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "OK"

def start_dummy_server():
    flask_app.run(host="0.0.0.0", port=10000)

# === Запуск бота ===



LEVELS_PRICE_FILE = 'обновление/levels_price.json'

from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters


async def handle_level_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    user_balances = load_balance(username)

    if user_balances is None:
        await update.message.reply_text("Ты ещё не начал приключение. Получи сначала печеньки!")
        return

    current_level = user_balances.get("уровень", 1)
    if current_level >= 20:
        await update.message.reply_text("Ты уже достиг максимального уровня!")
        return

    # ✅ Загрузка всех документов с ценами
    levels_price = {}
    docs = db.collection("levels_price").stream()
    for doc in docs:
        levels_price[doc.id] = doc.to_dict().get("цена")

    next_level = str(current_level + 1)
    price = levels_price.get(next_level)
    if price is None:
        await update.message.reply_text("Не могу определить цену повышения уровня.")
        return

    # Навык "Стратег" — скидка на цену печенек
    strategy_level = user_balances.get("навыки", {}).get("Стратег", 0)
    discount_percent = min(strategy_level * 5, 50)  # максимум 50%
    discounted_price = int(price * (100 - discount_percent) / 100)

    current_cookies = user_balances.get("печеньки", 0)
    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    resources = list(map(int, resources_str.split('/')))

    gold_cookies_index = list(RESOURCES.keys()).index("р")
    diamonds_index = list(RESOURCES.keys()).index("а")

    required_gold_cookies = 10 * (current_level - 9) if current_level >= 10 else 0
    required_diamonds = 10 * (current_level - 9) if current_level >= 10 else 0

    if current_level >= 10:
        if resources[gold_cookies_index] < required_gold_cookies:
            await update.message.reply_text(
                f"❗ Для повышения до {next_level} уровня нужно {required_gold_cookies} золотых печенек.")
            return
        if resources[diamonds_index] < required_diamonds:
            await update.message.reply_text(
                f"❗ Для повышения до {next_level} уровня нужно {required_diamonds} алмазов.")
            return

    if current_cookies < discounted_price:
        await update.message.reply_text(
            f"❗ Для повышения до {next_level} уровня нужно {discounted_price} 🍪 печенек (с учётом скидки Стратега).")
        return

    user_balances["печеньки"] = current_cookies - discounted_price
    if current_level >= 10:
        resources[gold_cookies_index] -= required_gold_cookies
        resources[diamonds_index] -= required_diamonds

    user_balances["уровень"] = current_level + 1
    user_balances["ресурсы"] = "/".join(map(str, resources))
    save_balance(username, user_balances)

    try:
        log_transaction({
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "type": "повысить уровень",
            "username": username,
            "from_level": current_level,
            "to_level": current_level + 1,
            "cookies_spent": discounted_price,
            "gold_cookies_spent": required_gold_cookies,
            "diamonds_spent": required_diamonds
        })
    except Exception as e:
        print(f"[Лог ошибка] Уровень: {e}")

    await update.message.reply_text(
        f"🎉 {username}, ты повысил уровень до {next_level}!\n"
        f"Ты потратил {discounted_price} 🍪 печенек"
        + (f", {required_gold_cookies} золотых печенек и {required_diamonds} алмазов!" if current_level >= 10 else "!")
    )


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

async def handle_update_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.username != ADMIN_USERNAME:
        await update.message.reply_text("Команда доступна только администратору.")
        return

    text = update.message.text.strip()
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
    db.collection("levels_price").document("data").set(new_prices)

    await update.message.reply_text(f"Цены успешно обновлены: {prices_str}")

lottery_lock = threading.Lock()




import threading
import datetime
from telegram import Message, Update


import firebase_admin
from firebase_admin import credentials, firestore

# Инициализация (один раз)
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
balances_ref = db.collection("balances")

def load_balance(username: str) -> dict | None:
    doc = balances_ref.document(username).get()
    return doc.to_dict() if doc.exists else None

def save_balance(username: str, data: dict):
    balances_ref.document(username).set(data, merge=True)




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
    user_balances = load_balance(username)

    if user_balances is None:
        # Инициализируем нового игрока
        user_balances = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0"
        }
        save_balance(username, user_balances)

    level = user_balances.get("уровень", 1)

    lines = [f"Милашка {username}, вот твой баланс:",
             f"Уровень: {level}"]

    for curr, emoji in CURRENCIES.items():
        amount = user_balances.get(curr, 0)
        lines.append(f"{amount} {curr} {emoji}")

    # 🎟 Добавим количество билетов из лотереи
    lottery = load_lottery_firestore()
    ticket_range = lottery.get(username)
    if ticket_range and isinstance(ticket_range, list) and len(ticket_range) == 2:
        ticket_count = ticket_range[1] - ticket_range[0] + 1
        if ticket_count > 0:
            lines.append(f"{ticket_count} лотерейных билетов 🎟️ ")

    # Добавляем отображение ресурсов
    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    resources = list(map(int, resources_str.split('/')))

    lines.append("\nРесурсы:")
    for resource_short, resource_name in RESOURCES.items():
        index = list(RESOURCES.keys()).index(resource_short)
        amount = resources[index]
        limit = RESOURCE_LIMITS[resource_short](level)  # Получаем лимит для ресурса
        lines.append(f"  {amount}/{limit} {resource_name} ({resource_short})")
    if random.randint(1,100)<chanse_balance:
        await update.message.reply_text(f"\n промокод: {PROMO}\n".join(lines))
    else:
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


from datetime import timedelta, timezone

moscow_tz = timezone(timedelta(hours=3))

async def handle_want_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    user_balances = load_balance(username)

    if user_balances is None:
        user_balances = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0",
            "последний фарм": ""
        }
        save_balance(username, user_balances)

    last_farm_str = user_balances.get("последний фарм", "")
    if not can_farm_today(last_farm_str):
        await update.message.reply_text("Вы уже получали печеньки сегодня. Попробуйте завтра!")
        return

    level = user_balances.get("уровень", 1)
    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    resources = list(map(int, resources_str.split('/')))
    messages = []

    def try_add_resource(index: int, amount: int, resource_code: str, message_text: str):
        limit = RESOURCE_LIMITS[resource_code](level)
        before = resources[index]
        after = min(before + amount, limit)
        added = after - before
        if added > 0:
            resources[index] = after
            messages.append(message_text.replace("{count}", str(added)))

    # === Расчёт печенек с учётом навыка "Лудоман" ===
    cookies = get_cookies_by_level(level, user_balances)

    level_ludoman = user_balances.get("навыки", {}).get("Лудоман", 0)
    if level_ludoman > 0:
        fluctuation_percent = 2 * level_ludoman
        min_multiplier = 100 - fluctuation_percent
        max_multiplier = 100 + fluctuation_percent
        multiplier = random.randint(min_multiplier, max_multiplier) / 100
        cookies = int(cookies * multiplier)

    user_balances["печеньки"] = user_balances.get("печеньки", 0) + cookies

    # === Навык "Бесконечное Печенье" ===
    level_infinite_cookies = user_balances.get("навыки", {}).get("Бесконечное Печенье", 0)
    if level_infinite_cookies > 0:
        guaranteed_cookies = min(level_infinite_cookies, 10)
        user_balances["печеньки"] += guaranteed_cookies
        messages.append(f"🍪 Навык 'Бесконечное Печенье' подарил тебе {guaranteed_cookies} печенек!")

    # === Навык "Железный Голем" ===
    level_iron_golem = user_balances.get("навыки", {}).get("Железный Голем", 0)
    if level_iron_golem > 0:
        extra_chance = level_iron_golem * 10
        iron_bonus = extra_chance // 100
        iron_remainder = extra_chance % 100
        if iron_bonus > 0:
            try_add_resource(2, iron_bonus, "ж", f"💪 Железный Голем сработал! +{iron_bonus} железа.")
        if random.randint(1, 100) <= iron_remainder:
            try_add_resource(2, 1, "ж", "💪 Железный Голем сработал! +1 железо.")

    # === Навык "Дар природы" ===
    level_nature_gift = user_balances.get("навыки", {}).get("Дар природы", 0)
    if level_nature_gift > 0:
        chance = 15 * level_nature_gift
        guaranteed = chance // 100
        remainder = chance % 100
        if guaranteed > 0:
            try_add_resource(1, guaranteed, "п", f"🌿 Дар природы сработал! +{guaranteed} пшениц.")
        if random.randint(1, 100) <= remainder:
            try_add_resource(1, 1, "п", f"🌿 Дар природы сработал! +1 пшеница.")

    # === Навык "Глаз Алмаз" ===
    level_eye_diamond = user_balances.get("навыки", {}).get("Глаз Алмаз", 0)
    if level_eye_diamond > 0:
        chance = level_eye_diamond
        if random.randint(1, 100) <= chance:
            try_add_resource(3, 1, "а", f"💎 Глаз Алмаз сработал! +1 алмаз.")

    # === Навык "Фарм-маньяк" ===
    level_farm_maniac = user_balances.get("навыки", {}).get("Фарм-маньяк", 0)
    if level_farm_maniac > 0:
        chance = 10 + level_farm_maniac * 5
        possible_resources = [0, 1, 2, 3, 4]
        if random.randint(1, 100) <= chance:
            res_index = random.choice(possible_resources)
            resource_code = list(RESOURCES.keys())[res_index]
            try_add_resource(res_index, 1, resource_code,
                             f"🔥 Фарм-маньяк сработал! +1 {RESOURCES[resource_code]}. (Шанс: {chance}%)")

    # === Навык "Удачливый" ===
    level_lucky = user_balances.get("навыки", {}).get("Удачливый", 0)
    if level_lucky > 0:
        chance = (level_lucky // 5) + 2
        amount = (level_lucky // 5) + 1
        if random.randint(1, 100) <= chance:
            try_add_resource(5, amount, "и", f"🍀 Навык 'Удачливый' сработал! +{amount} изумруда(ов).")

    # === Шансы на ресурсы по уровню ===
    if level >= 2:
        gold_chance = max(0, 25 - 5 * level)
        if random.randint(1, 100) <= gold_chance:
            try_add_resource(4, 1, "з", f"Вы получили {{count}} золото! (Шанс: {gold_chance}%)")

    iron_chance_total = 20 + 5 * level
    iron_count = iron_chance_total // 100
    if random.randint(1, 100) <= (iron_chance_total % 100):
        iron_count += 1
    if iron_count > 0:
        try_add_resource(2, iron_count, "ж", f"Вы получили {{count}} железа! (Шанс: {iron_chance_total}%)")

    if random.randint(1, 100) <= 1:
        user_balances["печеньки"] += 10
        messages.append("Вы получили 10 дополнительных печенек! (Шанс: 1%)")

    wheat_chance = max(0, 50 - 5 * level)
    if random.randint(1, 100) <= wheat_chance:
        try_add_resource(1, 1, "п", f"Вы получили {{count}} пшеницу! (Шанс: {wheat_chance}%)")

    cocoa_chance = 5
    if random.randint(1, 100) <= cocoa_chance:
        try_add_resource(0, 1, "к", f"Вы получили {{count}} какао-боб! (Шанс: {cocoa_chance}%)")

    if 2 <= level <= 5:
        diamond_chance = max(0, 30 - 5 * level)
        if random.randint(1, 100) <= diamond_chance:
            try_add_resource(3, 1, "а", f"Вы получили {{count}} алмаз! (Шанс: {diamond_chance}%)")

    if 1 <= level <= 10:
        emerald_chance = 3
        if random.randint(1, 100) <= emerald_chance:
            try_add_resource(5, 1, "и", f"Вы получили {{count}} изумруд! (Шанс: {emerald_chance}%)")

    user_balances["ресурсы"] = "/".join(map(str, resources))
    level_eternal_farm = user_balances.get("навыки", {}).get("Вечный Фарм", 0)
    chance_eternal = min(level_eternal_farm, 20)

    if level_eternal_farm > 0 and random.randint(1, 100) <= chance_eternal:
        messages.append(f"✨ Навык 'Вечный Фарм' сработал! Вы можете фармить ещё раз сегодня.")
    else:
        user_balances["последний фарм"] = datetime.now().strftime("%H:%M %d-%m-%Y")

    save_balance(username, user_balances)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "хочу печеньки",
            "from": "бот",
            "to": username,
            "currency": "печеньки",
            "amount": cookies
        })
    except:
        pass

    messages.insert(0, f"Вы получили {cookies} 🍪 печенек! Ваш уровень: {level}")
    try:
        await update.message.reply_text("\n".join(messages))
    except:
        pass


async def handle_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()
    recipient_tag = None
    recipient_match = re.search(r'@(\w+)', text)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    await debug_log_text(
        f"[GIVE] от {msg.from_user.username} даёт {text} → {recipient_tag or '❓неизвестно'}",
        context
    )

    match = re.match(r'^дать\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?\b', text, re.IGNORECASE)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: дать <количество> [название валюты]")
        return

    amount = int(match.group(1))
    if amount <= 0:
        await msg.reply_text("Количество должно быть положительным числом.")
        return

    currency_text = match.group(2)
    currency = "печеньки"
    if currency_text:
        currency_text = currency_text.lower()
        if currency_text in ("трилистника", "трилистники"):
            currency = "трилистники"
        elif currency_text in ("четырёхлистника", "четырёхлистники"):
            currency = "четырёхлистники"

    recipient_tag = None
    recipient_match = re.search(r'@(\w+)', text)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи тег красавчика или ответь на его сообщение.")
        return

    sender = get_username_from_message(msg)
    recipient = f"@{recipient_tag}"

    if sender == recipient:
        await msg.reply_text("Нельзя переводить себе!")
        return

    sender_data = load_balance(sender)
    if sender_data is None:
        sender_data = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0",
            "последний фарм": ""
        }
        save_balance(sender, sender_data)

    recipient_data = load_balance(recipient)
    if recipient_data is None:
        recipient_data = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0",
            "последний фарм": ""
        }
        save_balance(recipient, recipient_data)
    sender_balances = load_balance(sender)
    recipient_balances = load_balance(recipient)

    if sender_balances.get(currency, 0) < amount:
        await msg.reply_text(f"Кажется, в мешочке не хватает {currency}.")
        return

    sender_balances[currency] -= amount
    recipient_balances[currency] += amount

    save_balance(sender, sender_balances)
    save_balance(recipient, recipient_balances)

    try:
        log_transaction({
            "timestamp": datetime.now(timezone(timedelta(hours=3))).isoformat(),
            "type": "дать",
            "from": str(sender),
            "to": str(recipient),
            "currency": currency,
            "amount": amount
        })
    except Exception:
        pass

    try:
        await msg.reply_text(f"{sender} дружески отдал {amount} {currency} {CURRENCIES.get(currency, '')} {recipient}.")
    except:
        await msg.reply_text("Передача прошла, но не получилось отправить сообщение о ней.")





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
        reply_user = msg.reply_to_message.from_user
        if reply_user and reply_user.username:
            recipient_tag = reply_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи красавчика или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    recipient_balances = load_balance(recipient)

    if recipient_balances is None:
        recipient_balances = {curr: 0 for curr in CURRENCIES}

    recipient_balances[currency] = recipient_balances.get(currency, 0) + amount

    save_balance(recipient, recipient_balances)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "дар",
            "from": "Администрация",
            "to": recipient,
            "currency": currency,
            "amount": amount
        })
    except:
        pass  # логирование не помешает выполнению

    try:
        await msg.reply_text(f"{recipient} награждается {amount} {currency} {CURRENCIES.get(currency, '')} от администрации")
    except:
        await msg.reply_text("Передача прошла, но сообщение не получилось отправить.")





async def handle_take_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    match = re.match(
        r'^отнять\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?(?:\s+@(\w+))?',
        text, re.IGNORECASE
    )
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
        reply_user = msg.reply_to_message.from_user
        if reply_user and reply_user.username:
            recipient_tag = reply_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи красавчика или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    recipient_balances = load_balance(recipient)

    if recipient_balances is None:
        recipient_balances = {curr: 0 for curr in CURRENCIES}

    current = recipient_balances.get(currency, 0)
    recipient_balances[currency] = max(0, current - amount)

    save_balance(recipient, recipient_balances)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "отнять",
            "from": "Администрация",
            "to": recipient,
            "currency": currency,
            "amount": amount
        })
    except:
        pass  # если лог не сработал — просто игнорируем

    try:
        await msg.reply_text(f"{recipient} лишился {amount} {currency} {CURRENCIES.get(currency, '')}")
    except:
        await msg.reply_text("Печеньки отняты, но сообщение не отправилось.")



async def handle_save_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_username_from_message(update.message) != f"@{ADMIN_USERNAME}":
        return

    admin_chat_id = 844673891

    try:
        # 🔄 Баланс
        all_docs = balances_ref.stream()
        balances = {doc.id: doc.to_dict() for doc in all_docs}
        balance_content = json.dumps(balances, ensure_ascii=False, indent=2)

        # 📈 Цены уровней
        levels_collection = db.collection("levels_price").stream()
        levels_dict = {doc.id: doc.to_dict().get("цена") for doc in levels_collection}
        levels_content = json.dumps(levels_dict, ensure_ascii=False, indent=2)

        # 🎟️ Лотерея
        lottery = load_lottery_firestore()
        lottery_content = json.dumps(lottery, ensure_ascii=False, indent=2)

        # 📤 Отправка администратору
        for title, content in [("Баланс", balance_content), ("Цены уровней", levels_content),
                               ("Лотерея", lottery_content)]:
            if len(content) <= 4000:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"📂 *{title}*\n```json\n{content}\n```",
                    parse_mode="Markdown"
                )
            else:
                temp_path = f"{title}.json"
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                await context.bot.send_document(chat_id=admin_chat_id, document=open(temp_path, "rb"))
                os.remove(temp_path)

    except Exception as e:
        await context.bot.send_message(chat_id=admin_chat_id, text=f"❌ Ошибка: {e}")




async def handle_clear_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_username_from_message(update.message) != f"@{ADMIN_USERNAME}":
        await update.message.reply_text("Эта команда только для админа.")
        return

    docs = db.collection("lottery").stream()
    for doc in docs:
        db.collection("lottery").document(doc.id).delete()

    await update.message.reply_text("🎟️ Все билеты лотереи очищены.")



async def handle_average_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_docs = balances_ref.stream()
    balances = {doc.id: doc.to_dict() for doc in all_docs}
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
    await update.message.reply_text(f"Среднее количество печенек у милах (без крутых админов): {average:.2f} 🍪")
async def handle_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    is_admin = (username == f"@{ADMIN_USERNAME}")



    # Для обычных пользователей покажем только команды без пометки (админ)
    if not is_admin:
        filtered_commands = {cmd: desc for cmd, desc in commands_common.items() if "(админ)" not in desc}
    else:
        filtered_commands = commands_common

    lines = ["Тебе красавчик доступное следующее:"]
    for cmd, desc in filtered_commands.items():
        lines.append(f"{cmd} — {desc}")

    await update.message.reply_text("\n".join(lines))
async def handle_commands_not_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    filtered_commands = {cmd: desc for cmd, desc in commands_common.items() if "(админ)" not in desc}
    lines = ["Тебе красавчик доступное следующее:"]
    for cmd, desc in filtered_commands.items():
        lines.append(f"{cmd} — {desc}")
    await update.message.reply_text("\n".join(lines))
async def handle_commands_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    if username != f"@{ADMIN_USERNAME}":
        return  # Молчим, если не админ

    lines = ["📋 Полный список команд (включая админские):"]
    for cmd, desc in commands_common.items():
        lines.append(f"{cmd} — {desc}")
    await update.message.reply_text("\n".join(lines))

def get_cookies_by_level(level: int, user_balances: dict) -> int:
    fortune_level = user_balances.get("навыки", {}).get("Фортуна", 0)
    cfg = level_config.get(level, (0, 1, [0.5, 0.5]))
    min_val, max_val, weights = cfg
    values = list(range(min_val, max_val + 1))
    cookies = random.choices(values, weights=weights, k=1)[0]

    if fortune_level > 0:
        chance = 3 * fortune_level
        if random.randint(1, 100) <= chance:
            cookies *= 2

    return cookies

excluded_users = {"@hto_i_taki", "@Shittttt", "@zZardexe", "@insanemaloy"}  # админы
excluded_users_Admin = {"@hto_i_taki", "@Eparocheck"}  # исключить полностью

async def handle_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    group_username = "@WardShield3"

    try:
        member = await context.bot.get_chat_member(group_username, user_id)
        if member.status not in ("member", "administrator", "creator"):
            return  # Не участник — молчим
    except:
        return  # Ошибка — тоже молчим

    all_docs = balances_ref.stream()
    balances = {doc.id: doc.to_dict() for doc in all_docs}

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

    top_cookies_no_admins = sorted(
        balances_no_admins.items(),
        key=lambda x: x[1].get("печеньки", 0),
        reverse=True
    )[:5]

    top_levels = sorted(
        balances_no_admin_global.items(),
        key=lambda x: x[1].get("уровень", 1),
        reverse=True
    )[:5]

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

GROUP_USERNAME = "@WardShield3"  # Юзернейм группы

async def handle_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        member = await context.bot.get_chat_member(GROUP_USERNAME, user_id)
        if member.status not in ("member", "administrator", "creator"):
            return  # Не участник — молчим
    except:
        return  # Ошибка запроса или бот не в группе — тоже молчим

    await update.message.reply_text(
        "📌 <b>WardShield Server Info</b>\n\n"
        "💬 <b>Telegram чат:</b> <a href='https://t.me/WardShield3'>вступить</a>\n"
        "🌐 <b>IP:</b> <code>WardShield_3.aternos.me</code>\n"
        "🎮 <b>Версия Minecraft:</b> 1.21.1",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


def load_lottery_firestore():
    docs = db.collection("lottery").stream()
    return {doc.id: doc.to_dict().get("номера", []) for doc in docs}

def save_lottery_firestore(data: dict):
    lottery_ref = db.collection("lottery")
    for user, ticket_range in data.items():
        lottery_ref.document(user).set({"номера": ticket_range})






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

    user_data = load_balance(username)
    if user_data is None:
        user_data = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0",
            "последний фарм": ""
        }

    current_cookies = user_data.get("печеньки", 0)
    if current_cookies < count:
        await msg.reply_text("В твоём мешочке с Печеньками не хватает :(")
        return

    # Вычитаем печеньки
    user_data["печеньки"] = current_cookies - count
    save_balance(username, user_data)

    # Загрузка текущих билетов
    lottery = load_lottery_firestore()
    ordered = list(lottery.items())

    # Найдём текущего пользователя и его количество билетов
    current_index = next((i for i, (user, _) in enumerate(ordered) if user == username), None)
    previous_tickets = 0

    if current_index is not None:
        prev_range = ordered[current_index][1]
        previous_tickets = prev_range[1] - prev_range[0] + 1
        ordered.pop(current_index)

    total_tickets = previous_tickets + count
    ordered.append((username, [0, 0]))  # Добавим позже

    # Пересчёт диапазонов
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
    save_lottery_firestore(updated_lottery)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "Лото-Печенько-Рея",
            "from": username,
            "to": "лотерея",
            "currency": "печеньки",
            "amount": count
        })
    except:
        pass

    try:
        if random.randint(1, 100) < chanse_N:
            await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪 ай молодец, держи промо: {PROMO}")
        else:
            await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪 ай молодец")
    except:
        pass

async def handle_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(UPDATE_LOG.strip())


import os
import json

async def handle_show_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    if username != f"@{ADMIN_USERNAME}":
        await update.message.reply_text("Эта команда доступна только админу.")
        return

    lottery =load_lottery_firestore()
    if not lottery:
        await update.message.reply_text("Файл с билетами пуст.")
        return

    json_text = json.dumps(lottery, ensure_ascii=False, indent=2, separators=(',', ': '))


    if len(json_text) > 4000:
        temp_path = "обновление/lottery.json"
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
RESOURCE_LIMITS = {
    "к": lambda level: level,  # Какао-бобы: 1 * уровень
    "п": lambda level: level,  # Пшеница: 1 * уровень
    "ж": lambda level: 10 * level,  # Железо: 10 * уровень
    "а": lambda level: 3 * level,  # Алмазы: 3 * уровень
    "з": lambda level: 5 * level,  # Золото: 5 * уровень
    "и": lambda level: level,  # Изумруды: 1 * уровень
    "р": lambda level: level  # Золотая печенька: 1 * уровень
}
def get_user_resources(username, balances):
    user_data = balances.get(username, {})
    resources_str = user_data.get("ресурсы", "0/0/0/0/0/0/0")
    return list(map(int, resources_str.split('/')))
def update_user_resources(username, resources):
    user_data = load_balance(username)
    if user_data is None:
        user_data = {
            "уровень": 1,
            **{curr: 0 for curr in CURRENCIES},
            "ресурсы": "0/0/0/0/0/0/0",
            "последний фарм": ""
        }

    user_data["ресурсы"] = '/'.join(map(str, resources))
    save_balance(username, user_data)
def get_user_resources_from_data(user_data: dict) -> list[int]:
    raw = user_data.get("ресурсы", "0/0/0/0/0/0/0")
    return list(map(int, raw.split("/")))

async def handle_give_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    if not text.lower().startswith("рес дать"):
        await msg.reply_text("Команда должна начинаться с 'рес дать'.")
        return

    command = re.sub(r'^рес\s+дать', '', text, flags=re.IGNORECASE).strip()
    match = re.match(r'^(\d+)\s+(\w)', command)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: рес дать <количество> <ресурс> [@имя или ответом]")
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()

    if resource_short not in RESOURCES:
        await msg.reply_text("Такого ресурса не существует.")
        return

    resource_name = RESOURCES[resource_short]
    sender = get_username_from_message(msg)
    recipient_tag = None

    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи @username получателя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"

    if sender == recipient:
        await msg.reply_text("Нельзя переводить ресурсы самому себе.")
        return

    # Загрузка балансов
    sender_data = load_balance(sender)
    recipient_data = load_balance(recipient)

    if sender_data is None or recipient_data is None:
        await msg.reply_text("Один из участников не зарегистрирован.")
        return

    # Получение и проверка ресурсов
    sender_resources = get_user_resources_from_data(sender_data)
    recipient_resources = get_user_resources_from_data(recipient_data)

    resource_index = list(RESOURCES.keys()).index(resource_short)
    sender_level = sender_data.get("уровень", 1)
    recipient_level = recipient_data.get("уровень", 1)

    sender_limit = RESOURCE_LIMITS[resource_short](sender_level)
    recipient_limit = RESOURCE_LIMITS[resource_short](recipient_level)

    if sender_resources[resource_index] < amount:
        await msg.reply_text(f"У тебя не хватает {resource_name}.")
        return

    if recipient_resources[resource_index] + amount > recipient_limit:
        await msg.reply_text(f"У {recipient} нет места для {amount} {resource_name}.")
        return

    # Передача ресурсов
    sender_resources[resource_index] -= amount
    recipient_resources[resource_index] += amount

    update_user_resources(sender, sender_resources)
    update_user_resources(recipient, recipient_resources)

    try:
        log_transaction({
            "timestamp": datetime.now(timezone(timedelta(hours=3))).isoformat(),
            "type": "ресурс перевод",
            "from": sender,
            "to": recipient,
            "resource": resource_name,
            "amount": amount
        })
    except:
        pass

    await msg.reply_text(f"{sender} перевёл {amount} {resource_name} {recipient}.")





async def handle_give_admin_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    command = re.sub(r'^рес\s+дар', '', text, flags=re.IGNORECASE).strip()

    match = re.match(r'^(\d+)\s+(\w)', command)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: рес дар <количество> <ресурс> [@имя или ответом]")
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()

    if resource_short not in RESOURCES:
        await msg.reply_text("Неизвестный ресурс.")
        return

    resource_name = RESOURCES[resource_short]
    recipient_tag = None

    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя через @username или ответом на сообщение.")
        return

    recipient = f"@{recipient_tag}"
    recipient_data = load_balance(recipient)

    if recipient_data is None:
        await msg.reply_text("Получатель не зарегистрирован.")
        return

    recipient_resources = get_user_resources_from_data(recipient_data)
    recipient_level = recipient_data.get("уровень", 1)

    resource_index = list(RESOURCES.keys()).index(resource_short)
    recipient_limit = RESOURCE_LIMITS[resource_short](recipient_level)

    if recipient_resources[resource_index] + amount > recipient_limit:
        await msg.reply_text(f"У {recipient} нет места для {amount} {resource_name}.")
        return

    recipient_resources[resource_index] += amount
    update_user_resources(recipient, recipient_resources)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "ресурс дар",
            "from": "Администрация",
            "to": recipient,
            "resource": resource_name,
            "amount": amount
        })
    except:
        pass

    await msg.reply_text(f"{recipient} получил {amount} {resource_name} от администрации.")




async def handle_take_admin_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    command = re.sub(r'^рес\s+отнять', '', text, flags=re.IGNORECASE).strip()

    match = re.match(r'^(\d+)\s+(\w)', command)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: рес отнять <количество> <ресурс> [@имя или ответом]")
        return

    amount = int(match.group(1))
    resource_short = match.group(2).lower()

    if resource_short not in RESOURCES:
        await msg.reply_text("Неизвестный ресурс.")
        return

    resource_name = RESOURCES[resource_short]
    recipient_tag = None

    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя через @username или ответом на сообщение.")
        return

    recipient = f"@{recipient_tag}"
    recipient_data = load_balance(recipient)

    if recipient_data is None:
        await msg.reply_text("Получатель не зарегистрирован.")
        return

    recipient_resources = get_user_resources_from_data(recipient_data)
    resource_index = list(RESOURCES.keys()).index(resource_short)

    if recipient_resources[resource_index] < amount:
        await msg.reply_text(f"У {recipient} нет {amount} {resource_name} для изъятия.")
        return

    recipient_resources[resource_index] -= amount
    update_user_resources(recipient, recipient_resources)

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "ресурс изъятие",
            "from": recipient,
            "to": "Администрация",
            "resource": resource_name,
            "amount": amount
        })
    except:
        pass

    await msg.reply_text(f"{recipient} лишился {amount} {resource_name}.")


import re

from datetime import datetime, timedelta, timezone



async def handle_craft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    match = re.match(
        r'^крафт\s+(\d+)\s+(печенька|печеньки|печенек|золотая печенька|золотых печенек|золотых печеньек|золото)$',
        text, re.IGNORECASE
    )
    if not match:
        await msg.reply_text("Неверный формат. Используйте: крафт <кол-во> <печенька|золотая печенька>")
        return

    amount = int(match.group(1))
    craft_raw = match.group(2).lower()

    craft_type = "золотая печенька" if "золот" in craft_raw or craft_raw == "золото" else "печенька"

    username = get_username_from_message(msg)
    if not username:
        await msg.reply_text("Ошибка: не удалось определить пользователя.")
        return

    user_balances = load_balance(username)
    if user_balances is None:
        await msg.reply_text("Вы не зарегистрированы. Напишите Баланс для начала.")
        return

    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    try:
        resources = list(map(int, resources_str.split('/')))
    except ValueError:
        await msg.reply_text("Ошибка чтения ресурсов. Обратитесь к администратору.")
        return

    try:
        wheat_index = list(RESOURCES.keys()).index("п")
        cocoa_index = list(RESOURCES.keys()).index("к")
        gold_cookie_index = list(RESOURCES.keys()).index("р")
    except ValueError:
        await msg.reply_text("Ошибка конфигурации ресурсов.")
        return

    if craft_type == "печенька":
        econ_level = user_balances.get("навыки", {}).get("Экономист", 0)
        level = user_balances.get("уровень", 1)

        required_wheat = 2 * amount
        required_cocoa = 1 * amount
        bonus_cookies = 0

        if econ_level > 0:
            if 2 <= level < 5:
                required_wheat = max(0, required_wheat - 1 * amount)
            elif 5 <= level < 10:
                required_wheat = max(0, required_wheat - 2 * amount)
            elif level >= 10:
                required_wheat = 0
                bonus_cookies = 2 * amount

        if resources[wheat_index] < required_wheat or resources[cocoa_index] < required_cocoa:
            await msg.reply_text(f"Не хватает ресурсов для крафта {amount} обычных печенек.")
            return

        resources[wheat_index] -= required_wheat
        resources[cocoa_index] -= required_cocoa

        skill_level = user_balances.get("навыки", {}).get("Пекарь", 0)
        baked_cookies = amount + bonus_cookies
        if skill_level > 0:
            chance = 10 * skill_level
            extra_bonus = sum(1 for _ in range(amount) if random.randint(1, 100) <= chance)
            baked_cookies += extra_bonus

        user_balances["печеньки"] = user_balances.get("печеньки", 0) + baked_cookies

        try:
            log_transaction({
                "timestamp": datetime.now(moscow_tz).isoformat(),
                "type": "крафт",
                "username": username,
                "resource": "печенька",
                "amount": baked_cookies
            })
        except:
            pass

        await msg.reply_text(
            f"Вы скрафтили {baked_cookies} обычных печенек (включая бонус {bonus_cookies} от навыка 'Пекарь')."
        )

    elif craft_type == "золотая печенька":
        required_wheat = 2 * amount
        required_cocoa = 1 * amount
        required_cookies = 1 * amount

        if (
            resources[wheat_index] < required_wheat or
            resources[cocoa_index] < required_cocoa or
            user_balances.get("печеньки", 0) < required_cookies
        ):
            await msg.reply_text(f"Не хватает ресурсов для крафта {amount} золотых печенек.")
            return

        skill_level = user_balances.get("навыки", {}).get("Ювелир", 0)
        chance = 10 * skill_level

        def deduct_with_chance(total_needed, resource_index):
            spent = 0
            for _ in range(total_needed):
                if skill_level > 0 and random.randint(1, 100) <= chance:
                    continue
                resources[resource_index] -= 1
                spent += 1
            return spent

        spent_wheat = deduct_with_chance(required_wheat, wheat_index)
        spent_cocoa = deduct_with_chance(required_cocoa, cocoa_index)

        spent_cookies = 0
        for _ in range(required_cookies):
            if skill_level > 0 and random.randint(1, 100) <= chance:
                continue
            user_balances["печеньки"] -= 1
            spent_cookies += 1

        resources[gold_cookie_index] += amount

        ilon_level = user_balances.get("навыки", {}).get("Илон Маск", 0)
        if ilon_level > 0 and amount >= 3:
            bonus_cookies = 3 * ilon_level
            user_balances["печеньки"] += bonus_cookies
            await msg.reply_text(f"🚀 Навык 'Илон Маск' сработал! Вы получили дополнительно {bonus_cookies} обычных печенек.")

        try:
            log_transaction({
                "timestamp": datetime.now(moscow_tz).isoformat(),
                "type": "крафт",
                "username": username,
                "resource": "золотая печенька",
                "amount": amount
            })
        except:
            pass

        await msg.reply_text(
            f"Вы скрафтили {amount} золотых печенек! "
            f"Потрачено: пшеницы {spent_wheat}, какао-бобов {spent_cocoa}, печенек {spent_cookies} "
            f"(навык 'Ювелир' сработал с шансом {chance}%)"
        )

    else:
        await msg.reply_text("Неизвестный тип. Пример: крафт 1 печенька / крафт 1 золотая печенька")
        return

    # ✅ Сохраняем результат
    user_balances["ресурсы"] = "/".join(map(str, resources))
    save_balance(username, user_balances)

async def handle_resources_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📦 *Ресурсы и формулы выпадения:*

выпадает при команде "Хочу Печенек"

- *🧱 Железо*  
Используется в будущих обновлениях.  
▸ Шанс выпадения: `20 + 5 × уровень`%  
▸ Каждые 100% дают 1 гарантированное железо. Остаток — шанс на дополнительное.  
Пример: Уровень 10 → `20 + 5×10 = 70%`. Уровень 20 → `120%` → 1 гарант. + 20% на 2-е.

- *🏆 Золото*  
Используется в крафте золотых печенек.  
▸ Шанс: `25 - 5 × уровень`% (если уровень ≥ 2)  
Пример: Уровень 2 → `15%`, уровень 5 → `0%`.

- *💎 Алмазы*  
Редкий ресурс для прокачки уровней.  
▸ Шанс: `30 - 5 × уровень`% (только с 2 до 5 уровня).  
Пример: Уровень 2 → `20%`, уровень 5 → `5%`.

- *🌾 Пшеница*  
Нужна для крафтов.  
▸ Шанс: `50 - 5 × уровень`%  
Пример: Уровень 1 → `45%`, уровень 5 → `25%`.

- *🍫 Какао-бобы*  
Используются в крафтах.  
▸ Фиксированный шанс: `5%`, не зависит от уровня.

- *💚 Изумруды*  
Редчайший ресурс.  
▸ Фиксированный шанс: `3%` (на уровнях от 1 до 10).

- *🏵 Золотые печеньки*  
▸ Крафт: `2 пшеницы + 1 какао-боб + 1 золото = 1 золотая печенька`.  
▸ Используются для получения высоких уровней.

- *🎁 Бонус-печеньки*  
▸ Есть `1%` шанс получить дополнительно 10 обычных печенек при сборе.
"""

    await update.message.reply_text(text, parse_mode="Markdown")

SHOP_KEYWORDS = [
    "магазин", "зачем нужны печеньки", "зачем нужны печенья",
    "куда тратить печеньки", "что делать с печеньками", "на что потратить печеньки",
    "можно ли купить", "продажа", "покупка", "как использовать печеньки",
    "обменять печеньки", "награды за печеньки"
]
MOSCOW_TZ = timezone(timedelta(hours=3))
import traceback
async def notify_admin_on_error(context, where: str, exception: Exception):
    time_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    tb = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    message = (
        f"⚠️ *Ошибка в боте!*\n"
        f"*Где:* `{where}`\n"
        f"*Когда:* `{time_str}`\n"
        f"*Тип:* `{type(exception).__name__}`\n"
        f"*Сообщение:* `{str(exception)}`\n"
        f"*Traceback:* ```{tb[-900:]}```"
    )

    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print("❌ Не удалось отправить сообщение админу:", e)
async def handle_random_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()
    match = re.match(r'^раздача\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', text, re.IGNORECASE)
    if not match:
        await msg.reply_text("Формат: раздача <min_уровень> <max_уровень> <кол-во игроков> <сумма>")
        return

    min_level = int(match.group(1))
    max_level = int(match.group(2))
    player_count = int(match.group(3))
    amount = int(match.group(4))

    # Загружаем всех пользователей из Firestore
    all_docs = balances_ref.stream()
    all_balances = {doc.id: doc.to_dict() for doc in all_docs}

    # Фильтруем кандидатов
    if min_level == 0 and max_level == 0:
        candidates = [
            user for user, data in all_balances.items()
            if user not in excluded_users_Admin and isinstance(data, dict)
        ]
    else:
        candidates = [
            user for user, data in all_balances.items()
            if user not in excluded_users_Admin and isinstance(data, dict)
               and min_level <= data.get("уровень", 1) <= max_level
        ]

    if len(candidates) < player_count:
        await msg.reply_text(
            f"Недостаточно игроков уровня от {min_level} до {max_level}. Нашли только: {len(candidates)}"
        )
        return

    selected_users = random.sample(candidates, player_count)

    for user in selected_users:
        user_data = all_balances.get(user)
        if user_data is None or not isinstance(user_data, dict):
            user_data = {
                "уровень": 1,
                **{curr: 0 for curr in CURRENCIES},
                "ресурсы": "0/0/0/0/0/0/0",
                "последний фарм": ""
            }

        user_data["печеньки"] = user_data.get("печеньки", 0) + amount
        save_balance(user, user_data)

        try:
            log_transaction({
                "timestamp": datetime.now(moscow_tz).isoformat(),
                "type": "раздача",
                "from": "бот",
                "to": user,
                "currency": "печеньки",
                "amount": amount
            })
        except:
            pass

    names = ', '.join(selected_users)
    await msg.reply_text(
        f"🎉 {amount} 🍪 выданы {player_count} игрокам уровня {min_level}–{max_level}: {names}"
    )



async def handle_ultrahelp_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()
    group_username = "@WardShield3"
    keywords = ["казино", "эмодзи", "ультхелп", "ультхелпы", "помощь"]

    try:
        member = await context.bot.get_chat_member(group_username, user_id)
        if member.status not in ("member", "administrator", "creator"):
            return  # Не участник — молчим
    except:
        return  # Ошибка — молчим

    if any(keyword in text for keyword in keywords):
        await update.message.reply_text(ULTRAHELP_INFO, parse_mode="Markdown")
async def handle_set_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PROMO
    username = get_username_from_message(update.message)

    if username != f"@{ADMIN_USERNAME}":
        return  # Молчим, если не админ

    args = update.message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text("Укажи текст промо. Пример: `промо Печеньки всем`")
        return

    PROMO = args[1].strip()
    await update.message.reply_text(f"✅ Промо обновлено: {PROMO}")
async def debug_log_text(text: str, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=844673891, text=text)

async def handle_skill_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    user = load_balance(username)

    if not user:
        await update.message.reply_text("Сначала начни приключение!")
        return

    skills = user.get("навыки", {})
    if not skills:
        await update.message.reply_text("У тебя ещё нет навыков. Получи их через команду 'получить навык'")
        return

    lines = ["🎓 Твои навыки:\n"]
    for name, lvl in skills.items():
        max_lvl = SKILLS.get(name, 10)
        effective_lvl = min(lvl, max_lvl)

        desc = "Описание не доступно"

        if name == "Золотые Руки":
            chance = 10 * effective_lvl
            desc = f"Из 2 пшеницы, 1 какао и 1 золота создаёт 2 золотые печеньки с шансом {chance}%"

        elif name == "Железный Голем":
            chance = 10 * effective_lvl
            desc = f"+{chance}% шанса на железо. При 100% — гарантировано, остаток как шанс дополнительно"

        elif name == "Бесконечное Печенье":
            desc = f"Ежедневно даёт {effective_lvl} печенек"

        elif name == "Лудоман":
            desc = f"Сбор печенек колеблется от -{2*effective_lvl}% до +{2*effective_lvl}%"

        elif name == "Золотоискатель":
            cost = max(1, 30 - effective_lvl)
            desc = f"Обмен {cost} железа на 1 золото"

        elif name == "Великий Шахтёр":
            chance = 20 * effective_lvl
            desc = f"+1 железо в день с шансом {chance}%"

        elif name == "Пекарь":
            desc = f"{10 * effective_lvl}% шанс получить +1 печеньку при крафте"

        elif name == "Ювелир":
            desc = f"{10 * effective_lvl}% шанс не потратить ресурс при крафте золотой печеньки"

        elif name == "Дар природы":
            desc = f"+{15 * effective_lvl}% шанс на пшеницу при фарме"

        elif name == "Глаз Алмаз":
            desc = f"+{1 * effective_lvl}% шанс на алмаз при фарме"

        elif name == "Селянин":
            gold = effective_lvl // 3
            iron = 10 + effective_lvl
            desc = f"Обмен 1 изумруда на {gold} золота и {iron} железа (раз в день)"

        elif name == "Фарм-маньяк":
            chance = 10 + effective_lvl * 5
            desc = f"{chance}% шанс доп. ресурса при фарме"

        elif name == "Экономист":
            reduction = (2 + effective_lvl) // 3
            desc = f"Снижает трату пшеницы на {reduction} при крафте"

        elif name == "Стратег":
            desc = f"Снижает стоимость Печенек на {5 * effective_lvl}%"

        elif name == "Удачливый":
            chance = effective_lvl // 5 + 2
            amount = effective_lvl // 5 + 1
            desc = f"Шанс {chance}% получить {amount} изумруда при фарме"

        elif name == "Илон Маск":
            bonus = 3 * effective_lvl
            desc = f"При крафте 3+ золотых печенек — {bonus} обычных в подарок"

        elif name == "вечный фарм":
            desc = f"Шанс {effective_lvl}% получить дополнительный фарм в день"

        elif name == "Копатель":
            bonus = effective_lvl // 2 + 1
            threshold = 10 * effective_lvl
            desc = f"+{bonus} железа в день, если у тебя ≥{threshold} ресурсов"

        elif name == "Фортуна":
            desc = f"Шанс {3 * effective_lvl}% удвоить фарм"

        elif name == "Разрушитель":
            desc = f"Удаляет {effective_lvl} железа у другого игрока (1 раз в день)"

        elif name == "Алхимик":
            desc = f"{5 * effective_lvl}% шанс улучшить ресурс (ж→п→а→и)"

        elif name == "Торговец":
            prices = {
                1: {"п": (10, 10), "к": (5, 10), "ж": (20, 10), "з": (10, 10), "а": (2, 10), "и": (2, 10)},
                2: {"п": (9, 10), "к": (5, 11), "ж": (18, 11), "з": (9, 11), "а": (2, 11), "и": (2, 11)},
                3: {"п": (8, 11), "к": (5, 12), "ж": (17, 12), "з": (8, 12), "а": (2, 12), "и": (2, 12)},
                4: {"п": (7, 12), "к": (4, 12), "ж": (15, 12), "з": (7, 12), "а": (2, 13), "и": (2, 13)},
                5: {"п": (7, 13), "к": (4, 13), "ж": (14, 13), "з": (7, 13), "а": (2, 13), "и": (2, 13)},
                6: {"п": (6, 13), "к": (4, 14), "ж": (13, 14), "з": (6, 14), "а": (2, 14), "и": (2, 14)},
                7: {"п": (6, 14), "к": (4, 14), "ж": (12, 14), "з": (6, 14), "а": (2, 15), "и": (2, 15)},
                8: {"п": (5, 15), "к": (3, 15), "ж": (11, 15), "з": (5, 15), "а": (2, 15), "и": (2, 15)},
                9: {"п": (5, 15), "к": (3, 16), "ж": (10, 16), "з": (5, 16), "а": (2, 16), "и": (2, 16)},
                10: {"п": (4, 16), "к": (3, 16), "ж": (10, 16), "з": (4, 16), "а": (2, 17), "и": (2, 17)},
            }
            p = prices.get(effective_lvl)
            if p:
                desc = "Обмен ресурсов на печеньки:\n" + "\n".join(
                    [f"  • {k} → {v[1]} печ. (за {v[0]} шт.)" for k, v in p.items()])
            else:
                desc = "Продаёт ресурсы в печеньки. Цены зависят от уровня."

        lines.append(f"• {name} — {lvl}/{max_lvl}\n  🔹 {desc}")

    lines.append("\n🛠 Доступные команды:")
    lines.append("• получить навык")
    lines.append("• прокачать навык <название>")
    lines.append("• использовать навык <название>")
    lines.append("💡 Стоимость прокачки навыка: (5 × текущий уровень) железа + 10 печенек")

    await update.message.reply_text("\n".join(lines))


async def handle_get_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    user = load_balance(username)

    if not user:
        await update.message.reply_text("Ты ещё не начал игру. Сначала начни приключение!")
        return

    resources_str = user.get("ресурсы", "0/0/0/0/0/0/0")
    try:
        resources = list(map(int, resources_str.split("/")))
    except ValueError:
        await update.message.reply_text("Ошибка чтения ресурсов.")
        return

    skills = user.setdefault("навыки", {})

    if len(skills) >= len(SKILLS):
        await update.message.reply_text("У тебя уже есть все доступные навыки!")
        return

    if len(skills) == 0:
        if resources[2] < 5:
            await update.message.reply_text("Нужно 5 железа для получения первого навыка.")
            return
        resources[2] -= 5
    else:
        if resources[5] < 5:
            await update.message.reply_text("Нужно 5 изумрудов для следующего навыка.")
            return
        resources[5] -= 5

    available_skills = [s for s in SKILLS if s not in skills]
    new_skill = random.choice(available_skills)
    skills[new_skill] = 1

    user["ресурсы"] = "/".join(map(str, resources))
    save_balance(username, user)

    await update.message.reply_text(f"Ты получил навык: {new_skill} (ур. 1)")



SKILLS = {
    "Золотые Руки": 10,
    "Железный Голем": 20,
    "Бесконечное Печенье": 10,
    "Лудоман": 10,
    "Золотоискатель": 10,
    "Великий Дар": 10,
    "Великий Шахтёр": 20,
    "Пекарь": 10,
    "Ювелир": 10,
    "Дар природы": 20,
    "Глаз Алмаз": 20,
    "Селянин": 20,
    "Переработчик": 20,
    "Фарм-маньяк": 10,
    "Экономист": 10,
    "Стратег": 10,
    "Удачливый": 10,
    "Илон Маск": 10,
    "Изобретатель": 10,
    "Второе дыхание": 20,
    "Торговец": 10,
    "Копатель": 10,
    "Фортуна": 10,
    "Разрушитель": 10,
    "Алхимик": 10
}
async def handle_upgrade_skill(update: Update, context: ContextTypes.DEFAULT_TYPE, skill_name: str):
    username = get_username_from_message(update.message)
    user = load_balance(username)

    if not user:
        await update.message.reply_text("Ты ещё не начал игру.")
        return

    skill_name_input = skill_name.strip().lower()
    skills = user.get("навыки", {})

    normalized_skills = {k.lower(): k for k in skills}
    if skill_name_input not in normalized_skills:
        await update.message.reply_text(f"У тебя нет навыка с названием \"{skill_name}\".")
        return

    original_name = normalized_skills[skill_name_input]
    level = skills[original_name]
    max_level = SKILLS.get(original_name, 10)

    if level >= max_level:
        await update.message.reply_text(
            f"Навык {original_name} уже прокачан до максимального уровня ({max_level})."
        )
        return

    player_level = user.get("уровень", 1)
    if level >= player_level:
        await update.message.reply_text(
            f"Нельзя повысить навык {original_name} выше твоего уровня ({player_level})."
        )
        return

    try:
        resources = list(map(int, user.get("ресурсы", "0/0/0/0/0/0/0").split("/")))
    except ValueError:
        await update.message.reply_text("Ошибка чтения ресурсов.")
        return

    cookies = user.get("печеньки", 0)

    cost_iron = 5 * level
    cost_cookies = 10
    cost_diamonds = 10 if (level + 1) % 10 == 0 else (5 if (level + 1) % 5 == 0 else 0)

    if resources[2] < cost_iron or cookies < cost_cookies or resources[3] < cost_diamonds:
        await update.message.reply_text(
            f"Недостаточно ресурсов:\n"
            f"- Нужно {cost_iron} железа\n"
            f"- Нужно {cost_cookies} печенек\n"
            f"- Нужно {cost_diamonds} алмазов"
        )
        return

    resources[2] -= cost_iron
    resources[3] -= cost_diamonds
    cookies -= cost_cookies

    skills[original_name] += 1
    user["ресурсы"] = "/".join(map(str, resources))
    user["печеньки"] = cookies
    save_balance(username, user)

    await update.message.reply_text(
        f"Навык {original_name} успешно прокачан до уровня {skills[original_name]}!"
    )



import random
from datetime import datetime

async def use_skill_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    username = get_username_from_message(msg)
    user_balances = load_balance(username)

    if user_balances is None:
        await msg.reply_text("Вы не зарегистрированы.")
        return

    text = msg.text.strip()
    parts = text.split(" ", 2)
    skills = user_balances.get("навыки", {})

    # Определение названия навыка
    if len(parts) < 3:
        if len(skills) == 1:
            skill_name = list(skills.keys())[0]
        else:
            await msg.reply_text("Укажи название навыка: например, использовать навык Пекарь")
            return
    else:
        skill_name = parts[2].strip().lower().title()

    skill_level = skills.get(skill_name, 0)
    if skill_level <= 0:
        await msg.reply_text(f"Навык '{skill_name}' не прокачан или не получен.")
        return

    # Подготовка ресурсов
    try:
        resources = list(map(int, user_balances.get("ресурсы", "0/0/0/0/0/0/0").split("/")))
    except ValueError:
        await msg.reply_text("Ошибка чтения ресурсов.")
        return

    messages = []
    res_codes = {"к": 0, "п": 1, "ж": 2, "а": 3, "з": 4, "и": 5}

    def save_resources():
        user_balances["ресурсы"] = "/".join(map(str, resources))

    def check_resources(reqs: dict) -> bool:
        return all(resources[res_codes[r]] >= amt for r, amt in reqs.items())

    def deduct_resources(reqs: dict):
        for r, amt in reqs.items():
            resources[res_codes[r]] -= amt

    # === НАВЫКИ ===
    if skill_name == "Золотые Руки":
        effective_level = min(skill_level, 10)
        reqs = {"п": 2, "к": 1, "з": 1}
        if check_resources(reqs):
            deduct_resources(reqs)
            chance = 10 * effective_level
            if random.randint(1, 100) <= chance:
                resources[6] += 2
                messages.append(f"✨ Навык '{skill_name}' сработал! Ты получил 2 золотых печеньки.")
            else:
                resources[6] += 1
                messages.append(f"Навык '{skill_name}' не сработал полностью, но ты получил 1 золотую печеньку.")
        else:
            messages.append("Недостаточно ресурсов для навыка 'Золотые Руки'. Нужно: 2 пшеницы, 1 какао-боб, 1 золото.")

    elif skill_name == "Железный Голем":
        messages.append("Навык 'Железный Голем' — пассивный, не требует использования.")

    elif skill_name == "Бесконечное Печенье":
        today_str = datetime.now().strftime("%d-%m-%Y")
        last_bonus = user_balances.get("бесконечное_печенье_дата", "")
        if last_bonus != today_str:
            user_balances["печеньки"] = user_balances.get("печеньки", 0) + skill_level
            user_balances["бесконечное_печенье_дата"] = today_str
            messages.append(f"Навык 'Бесконечное Печенье' активирован! Вам начислено {skill_level} печенек.")
        else:
            messages.append("Сегодня вы уже использовали 'Бесконечное Печенье'.")

    elif skill_name == "Лудоман":
        current_cookies = user_balances.get("печеньки", 0)
        max_change = max(int(current_cookies * 0.02 * skill_level), skill_level)
        change = random.randint(-max_change, max_change)
        user_balances["печеньки"] = max(0, current_cookies + change)
        messages.append(f"Навык 'Лудоман' сработал! Баланс печенек изменился на {change:+}.")

    elif skill_name == "Золотоискатель":
        cost = 30 - skill_level
        if resources[2] >= cost:
            resources[2] -= cost
            resources[4] += 1
            messages.append(f"Навык 'Золотоискатель' активирован! Потрачено {cost} железа, получено 1 золото.")
        else:
            messages.append(f"Недостаточно железа. Нужно {cost} железа.")

    elif skill_name == "Великий Дар":
        reqs = {"ж": 50 - skill_level, "з": 20 - skill_level, "а": 10, "п": 10, "к": 10}
        if check_resources(reqs):
            deduct_resources(reqs)
            resources[5] += 1
            messages.append("Навык 'Великий Дар' активирован! Получен 1 изумруд.")
        else:
            messages.append("Недостаточно ресурсов для 'Великого Дара'.")

    elif skill_name == "Великий Шахтёр":
        chance = 20 * skill_level
        gained = chance // 100 + (1 if random.randint(1, 100) <= (chance % 100) else 0)
        if gained:
            resources[2] += gained
            messages.append(f"Навык 'Великий Шахтёр' сработал! Получено {gained} железа.")
        else:
            messages.append("Навык 'Великий Шахтёр' не сработал.")

    elif skill_name == "Селянин":
        if resources[5] >= 1:
            resources[5] -= 1
            gold_amount = skill_level // 3
            iron_amount = 10 + skill_level
            def get_limit(code): return RESOURCE_LIMITS[code](user_balances.get("уровень", 1))
            resources[4] = min(resources[4] + gold_amount, get_limit("з"))
            resources[2] = min(resources[2] + iron_amount, get_limit("ж"))
            messages.append(f"Навык 'Селянин' сработал! Получено {gold_amount} золота и {iron_amount} железа.")
        else:
            messages.append("Недостаточно изумрудов для использования навыка 'Селянин'.")

    elif skill_name == "Торговец":
        prices = {
            1: {"п": (10, 10), "к": (5, 10), "ж": (20, 10), "з": (10, 10), "а": (2, 10), "и": (2, 10)},
            2: {"п": (9, 10), "к": (5, 11), "ж": (18, 11), "з": (9, 11), "а": (2, 11), "и": (2, 11)},
            3: {"п": (8, 11), "к": (5, 12), "ж": (17, 12), "з": (8, 12), "а": (2, 12), "и": (2, 12)},
            4: {"п": (7, 12), "к": (4, 12), "ж": (15, 12), "з": (7, 12), "а": (2, 13), "и": (2, 13)},
            5: {"п": (7, 13), "к": (4, 13), "ж": (14, 13), "з": (7, 13), "а": (2, 13), "и": (2, 13)},
            6: {"п": (6, 13), "к": (4, 14), "ж": (13, 14), "з": (6, 14), "а": (2, 14), "и": (2, 14)},
            7: {"п": (6, 14), "к": (4, 14), "ж": (12, 14), "з": (6, 14), "а": (2, 15), "и": (2, 15)},
            8: {"п": (5, 15), "к": (3, 15), "ж": (11, 15), "з": (5, 15), "а": (2, 15), "и": (2, 15)},
            9: {"п": (5, 15), "к": (3, 16), "ж": (10, 16), "з": (5, 16), "а": (2, 16), "и": (2, 16)},
            10: {"п": (4, 16), "к": (3, 16), "ж": (10, 16), "з": (4, 16), "а": (2, 17), "и": (2, 17)},
        }
        level_prices = prices.get(skill_level, prices[10])
        available = [(r, *level_prices[r]) for r in level_prices if resources[res_codes[r]] >= level_prices[r][0]]
        if available:
            r, cost, cookies = random.choice(available)
            resources[res_codes[r]] -= cost
            user_balances["печеньки"] = user_balances.get("печеньки", 0) + cookies
            messages.append(f"Навык 'Торговец': обмен {cost} {r} на {cookies} печенек.")
        else:
            messages.append("Недостаточно ресурсов для продажи через 'Торговца'.")

    elif skill_name in [
        "Фарм-маньяк", "Пекарь", "Ювелир", "Дар природы", "Глаз Алмаз",
        "Фортуна", "Удачливый", "Илон Маск", "Изобретатель", "вечный фарм"
    ]:
        messages.append(f"Навык '{skill_name}' — пассивный. Он работает автоматически.")

    else:
        messages.append(f"Навык '{skill_name}' не реализован или неизвестен.")

    save_balance(username, user_balances)
    await msg.reply_text("\n".join(messages))


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
    elif lower_text == "хочу печеньки" or lower_text == "хочу печенек" or lower_text == "дайте печенек"or lower_text == "дай печенек"or lower_text == "хороший котик":
        await handle_want_cookies(update, context)
        if random.random() < 0.2:
            await maybe_save_admin(update, context)
    elif lower_text == "повысить уровень" or lower_text == "поднять уровень" or lower_text == "Повысить уровень" :
        await handle_level_up(update, context)
        if random.random() < 0.25:
            await maybe_save_admin(update, context)
    elif lower_text.startswith("новые цены") and username == f"@{ADMIN_USERNAME}":
        await handle_update_prices(update, context)
    elif lower_text == "все команды":
        await handle_commands(update, context)
    elif lower_text == "команды":
        await handle_commands_not_admin(update, context)
    elif lower_text == "команды все":
        await handle_commands_all(update, context)
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
    elif lower_text == PROMO:
        await update.message.reply_text("@hto_i_taki промик нашли!")
    elif lower_text.startswith("рес дать") or lower_text.startswith("Рес дать"):
        await handle_give_resources(update, context)
    elif lower_text.startswith("рес дар") or lower_text.startswith("Рес дар"):
        await handle_give_admin_resources(update, context)
    elif lower_text.startswith("рес отнять") or lower_text.startswith("Рес отнять"):
        await handle_take_admin_resources(update, context)
    elif lower_text.startswith("крафт"):
        await handle_craft(update, context)
    elif lower_text == "ресурсы":
        await handle_resources_info(update, context)
    elif any(k in lower_text for k in ["казино", "эмодзи", "ультхелп", "ультхелпы"]):
        await handle_ultrahelp_keywords(update, context)
    elif lower_text in ["окак", "о как"]:
        await update.message.reply_text("отак", parse_mode="Markdown")
    elif any(keyword in lower_text for keyword in SHOP_KEYWORDS):
        await update.message.reply_text(SHOP_INFO, parse_mode="Markdown")
    elif re.search(r'\b(котик|кот|киса|кошак|котя|котёнок)\b', lower_text):
            await update.message.reply_text("Я хороший Котик!", parse_mode="Markdown")
    elif lower_text.startswith("раздача"):
        await handle_random_giveaway(update, context)
    elif lower_text.startswith("промо"):
        await handle_set_promo(update, context)
    elif lower_text == "навык":
        await handle_skill_info(update, context)
    elif lower_text == "получить навык":
        await handle_get_skill(update, context)
    elif lower_text.startswith("прокачать навык"):
        parts = lower_text.split(" ", 2)
        username = get_username_from_message(update.message)
        user = load_balance(username)

        if user is None:
            await update.message.reply_text("Ты ещё не начал игру.")
            return

        skills = user.get("навыки", {})

        if len(parts) < 3:
            if len(skills) == 1:
                skill_name = list(skills.keys())[0]
                await handle_upgrade_skill(update, context, skill_name)
            else:
                await update.message.reply_text(
                    "Укажи название навыка после команды. Например:\nпрокачать навык Пекарь")
        else:
            skill_name = parts[2].strip().lower().title()
            await handle_upgrade_skill(update, context, skill_name)

    elif lower_text == "использовать навык" or lower_text == "юзануть навык" or lower_text == "юз навык" or lower_text == "юз навыка":
        await use_skill_logic(update, context)






    elif random.randint(1,1000)<=chanse_vezde:
        await update.message.reply_text(f"Ты мне понравился, держи промо: {PROMO}")
    elif random.randint(1,1000)<=4:
        await update.message.reply_text(f"А ты любишь Печеньки?")
    elif random.randint(1,1000)<=2:
        await update.message.reply_text(f"Напиши \"N <число>\" что бы купить N билетиков")
    elif random.randint(1,1000)<=4:
        await update.message.reply_text(f"А ты сегодня уже получал Печеньки?")


PROMO = "ggkatka"# ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ПРОМОКОД✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
chanse_N = 10
chanse_balance = 1
chanse_vezde = 1
commands_common = {
    "🆕 обнова": "Показать список обновлений",
    "💰 баланс": "Показать текущий баланс и уровень",
    "🎁 дать <число>": "Передать печеньки другому игроку",
    "🎁 дар <число>": "Передать печеньки от администратора (админ)",
    "❌ отнять <число>": "Отнять печеньки у игрока (админ)",
    "💾 сохранение": "Сохранить данные (админ)",
    "🎲 показать": "Показать лотерею (админ)",
    "🧹 очистить": "Очистить лотерею (админ)",
    "📊 среднее": "Показать среднее количество печенек у игроков",
    "🍪 хочу печеньки": "Получить печеньки случайным образом",
    "📈 повысить уровень": "Повысить свой уровень, потратив печеньки",
    "🔁 новые цены": "Обновить цены на уровни (админ)",
    "🎟️ N <число>": "Купить указанное количество лотерейных билетов",
    "🏆 топ": "Топ 5 игроков по печенькам и уровням + топ без админов",
    "📚 уровень": "Информация о шансах и ценах для каждого уровня",
    "🗂 архив [все|число]": "Показать последние N или все транзакции (админ)",
    "📦 рес дать <число> <ресурс(одной буквой)>": "Передать ресурс другому игроку",
    "📦 рес дар <число> <ресурс>": "Передать ресурс от администратора (админ)",
    "📦 рес отнять <число> <ресурс>": "Отнять ресурс у игрока (админ)",
    "⚒️ крафт <количество> <печенек|золотых печенек>": "Скрафтить указанное количество обычных или золотых печенек",
    "🌾 ресурсы": "Описание всех ресурсов, их шансов выпадения и формул",
    "🆘 УльтХелп": "Информация о УльтХелпах Игроков",
    "🛍️ магазин": "Показать, что можно купить за печеньки, ресурсы",
    "📖 навык": "Показать список доступных навыков и их уровни",
    "✨ использовать навык <название>": "Активировать выбранный навык",
    "📈 прокачать навык <название>": "Повысить уровень указанного навыка",
    "🎓 получить навык": "Получить новый навык (если доступно)"
}

UPDATE_LOG = """
📦 Последние обновления 🛠:

✅ Понижены цены на повышение Уровнней
✅ Добавлены две особые и самые важные команды
✅ Добавлена команда "Магазин"
✅ Бот реагирует на "казино", "эмодзи", "ультхелп", "ультхелпы", "помощь" и выводит команду "ультхелп"
 Добавлена команда "Ресурсы" для объяснения 
 Обновлена команда "Уровень"
 Исправлена команда крафт
 Исправлена выдача железа
 Обновлены все фразы бота
 Добавлено условие для перехода на 11-й Уровень(на каждые 10 уровней)
 Максимальный Уровень прописан до 20-го
 Добавлены бонусы в команде "Хочу Печеньки"
 Добавлена команда крафт <количество> <печеньки|золотых печеньек> 
 Добавлена Пшеница, Какао-бобы, железо, золото, алмазы, изумруды ️
 Добавлена доп защита от отката в билетах ️
 Обновлена  фраза  в балансе ️
 Исправлена команда "N <число>" — покупка билетов 🎟️
 Команда "баланс" теперь показывает количество билетов
 Исправлена ошибка с покупкой 1 билета
 Оптимизирована функция сохранения лотереи
"""


async def handle_level_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Загружаем все цены уровней из отдельных документов
    prices = {}
    docs = db.collection("levels_price").stream()
    for doc in docs:
        prices[doc.id] = doc.to_dict().get("цена")

    lines = [
        "📊 *Уровни*",
        "Уровень увеличивает фарм печенек и открывает новые возможности. "
        "_Для прокачки высоких уровней потребуются ресурсы._\n"
    ]

    for level in range(1, 21):
        min_amt, max_amt, chances = level_config[level]
        chance_str = "/".join(f"{round(p * 100)}" for p in chances)
        if level == 1:
            price = "🚫"
        else:
            price = prices.get(str(level), "неизвестно")
        lines.append(f"*{level} ур*: {min_amt}–{max_amt} 🍪 в день | шанс: {chance_str}% | цена: {price}")

    lines.append("\n📉 *Откуп от поражения*")
    lines.append("Доступен при достижении нужного уровня. Цена — в 2 раза ниже.\n")
    lines.append("*Формат:* `(Ступень — Этап) : Уровень`")
    lines.append("""\n
📌 *Подготовительный Этап*
- 1 ст. : 2 ур
- 2 ст. : 4 ур
- 3 ст. : 6 ур
- Финал ПЭ : 8 ур

📌 *Основное Событие*
- 1 этап : 10 ур
- 2 этап : 12 ур
- 3 этап : 14 ур
- Финал : 🚫 откуп недоступен
""")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

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
    11: (3, 7, [0.1, 0.2, 0.5, 0.15, 0.05]),
    12: (3, 7, [0.1, 0.15, 0.55, 0.15, 0.05]),
    13: (3, 7, [0.05, 0.2, 0.55, 0.15, 0.05]),
    14: (3, 7, [0.05, 0.15, 0.6, 0.15, 0.05]),
    15: (4, 7, [0.15, 0.6, 0.15, 0.1]),
    16: (4, 7, [0.1, 0.6, 0.2, 0.1]),
    17: (4, 7, [0.05, 0.65, 0.2, 0.1]),
    18: (5, 7, [0.7, 0.2, 0.1]),
    19: (5, 7, [0.6, 0.3, 0.1]),
    20: (5, 7, [0.5, 0.4, 0.1]),

}
SHOP_INFO = """🛍️ *Добро пожаловать в Магазин Печенек!*
Теперь за Печеньки также можно купить:
🍪 3 часа у репетитора по программированию на *C++*  
💰 Цена: *4000 печенек*
🍪 2 часа у репетитора по *C#*  
💰 Цена: *3000 печенек*
🍪 2 часа у репетитора по *Python*  
💰 Цена: *2000 печенек*
📈 3 часа у репетитора по *Ценным Бумагам, биржам, трейдингу, акциям и заработку в интернете*  
💰 Цена: *5000 печенек*
🎁 *Скидка 50%* на часы у репетитора  
💰 Цена: *1 ☘️* или *5000 печенек*
🪜 Место на второй ступени *без сражения на первой*  
💰 Цена: *100 печенек*
🏆 Место в Финале Подготовительного Этапа *без сражений на ступенях*  
💰 Цена: *200 печенек*
🎯 Место в Первом Этапе *без участия в Подготовительном*  
💰 Цена: *300 печенек*
💎 Бонус-предложение:  
Продам *1 ☘️* первому желающему — *всего за 2 изумруда*!
📩 Для покупки пишите *Админу* (Ягами)
"""

ULTRAHELP_INFO = """🔮 *УльтХелп — Ультемативная Помощь от Создателя*

Позволяет расширить функциональность вашей механики (механика — это ваша идея/бизнес по заработку Печенек и т.п.).
УльтХелпы продаются за Печеньки. Каждый игрок может придумать свою механику (например, своё казино).

⚠️ *Предупреждение:* Прочитайте все УльтХелпы, чтобы случайно не потерять Печеньки!

🎰 *УльтХелп: Эмодзи Казино*
👤 Владелец: Gaster999  
📜 Описание:  
При использовании его эмодзи Казино вы автоматически участвуете в его казино.  
💸 *Условия казино от Gaster999:*  
• Стоимость игры: 1 Печенька  
• Приз за 3 в ряд: 5 Печенек  
🎮 Для игры переведите по 1 Печеньке за игру Gaster999 командой `дать 1` (с указанием на его сообщение или допишите его тег в конце) и киньте эмодзи казино.

🎲 *УльтХелп: Эмодзи Кубик*
👤 Владелец: Shittttt  
📜 Описание:  
При использовании его эмодзи Кубик вы автоматически участвуете в его игре *Покер*.

🎳 *УльтХелп: Эмодзи Боулинг*
👤 Владелец: nastysh3cka  
📜 Описание:  
При использовании её эмодзи Боулинг вы автоматически участвуете в её казино.  
💸 *Условия казино от nastysh3cka:*  
• Стоимость игры: 3 Печеньки  
• Приз за страйк: 6 Печенек  
🎮 Для игры переведите по 3 Печеньки за игру nastysh3cka командой `дать 3` (с указанием на её сообщение или допишите её тег в конце) и киньте эмодзи боулинг.  
Если вы просто кинете эмодзи Боулинг — вы автоматически соглашаетесь на оплату игры в казино.
"""


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


if __name__ == '__main__':
    # Заглушка Flask — в фоновом потоке
    threading.Thread(target=start_dummy_server, daemon=True).start()

    # Бот — в главном потоке
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Бот запущен...")
    app.run_polling()