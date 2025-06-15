
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
TOKEN = "7604409638:AAGQPicknQYWdp5MPVJQzGy3rJwBVCsiwCE"
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
        await update.message.reply_text("В твоём мешочке с Печеньками кажется не достаточно :(.")
        return

    current_level = user_balances.get("уровень", 1)
    if current_level >= 20:
        await update.message.reply_text("Ты и так слишком крут!")
        return

    levels_price = load_levels_price()
    next_level = str(current_level + 1)
    price = levels_price.get(next_level)

    if price is None:
        await update.message.reply_text("Не могу определить цену повышения уровня.")
        return

    current_cookies = user_balances.get("печеньки", 0)
    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    resources = list(map(int, resources_str.split('/')))

    gold_cookies_index = list(RESOURCES.keys()).index("р")
    diamonds_index = list(RESOURCES.keys()).index("а")

    required_gold_cookies = 10 * (current_level - 9) if current_level >= 10 else 0
    required_diamonds = 10 * (current_level - 9) if current_level >= 10 else 0

    if current_level >= 10:
        if resources[gold_cookies_index] < required_gold_cookies:
            await update.message.reply_text(f"Для повышения до уровня {next_level} нужно {required_gold_cookies} золотых Печенек, так что иди и найди их мне")
            return
        if resources[diamonds_index] < required_diamonds:
            await update.message.reply_text(f"Для повышения до уровня {next_level} нужно {required_diamonds} алмазов, так что иди и найди их мне")
            return

    if current_cookies < price:
        await update.message.reply_text(f"Для повышения до уровня {next_level} нужно {price} печенек, так что иди и найди их мне")
        return

    # Отнимаем ресурсы и повышаем уровень
    user_balances["печеньки"] = current_cookies - price
    if current_level >= 10:
        resources[gold_cookies_index] -= required_gold_cookies
        resources[diamonds_index] -= required_diamonds
    user_balances["уровень"] = current_level + 1
    user_balances["ресурсы"] = "/".join(map(str, resources))
    balances[username] = user_balances
    save_balances(balances)

    # Логируем действие
    log_transaction({
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "type": "повысить уровень",
        "username": username,
        "from_level": current_level,
        "to_level": current_level + 1,
        "cookies_spent": price,
        "gold_cookies_spent": required_gold_cookies if current_level >= 10 else 0,
        "diamonds_spent": required_diamonds if current_level >= 10 else 0
    })

    await update.message.reply_text(f"Поздравляю! Ты повысил уровень до {next_level} и потратил {price} печенек. Давай ещё повысим !")
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



file_lock = threading.Lock()

def load_balances():
    with file_lock:
        if not os.path.exists(BALANCE_FILE):
            return {}
        with open(BALANCE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

import random
import datetime
from telegram import Message, Update

file_lock1 = threading.Lock()

def save_balances(data):
    file_lock1.acquire()
    try:
        with open(BALANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    finally:
        file_lock1.release()



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
        user_balances.update({"ресурсы": "0/0/0/0/0/0/0"})  # Добавляем ресурсы
        balances[username] = user_balances
        save_balances(balances)  # сохраняем в файл

    level = user_balances.get("уровень", 1)

    lines = [f"Милашка {username}, вот твой баланс:",
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
    balances = load_balances()
    user_balances = balances.get(username)

    if user_balances is None:
        user_balances = {"уровень": 1}
        user_balances.update({curr: 0 for curr in CURRENCIES})
        user_balances.update({"ресурсы": "0/0/0/0/0/0/0"})
        user_balances.update({"последний фарм": ""})
        balances[username] = user_balances

    last_farm_str = user_balances.get("последний фарм", "")
    if not can_farm_today(last_farm_str):
        await update.message.reply_text("Вы уже получали печеньки сегодня. Попробуйте завтра!")
        return

    level = user_balances.get("уровень", 1)
    cookies = get_cookies_by_level(level)
    user_balances["печеньки"] = user_balances.get("печеньки", 0) + cookies

    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    resources = list(map(int, resources_str.split('/')))
    messages = []

    if level >= 2:
        gold_chance = 25 - 5 * level
        if random.randint(1, 100) <= gold_chance:
            resources[4] += 1
            messages.append(f"Вы получили 1 золото! (Шанс: {gold_chance}%)")

    iron_chance = 20 + 5 * level
    iron_count = 0

    while iron_chance >= 100:
        resources[2] += 1
        iron_count += 1
        iron_chance -= 100

    # остаток — шанс на дополнительное железо
    if iron_chance > 0 and random.randint(1, 100) <= iron_chance:
        resources[2] += 1
        iron_count += 1

    if iron_count > 0:
        messages.append(f"Вы получили {iron_count} железа! (Общий шанс: {20 + 5 * level}%)")

    if random.randint(1, 100) <= 1:
        user_balances["печеньки"] += 10
        messages.append("Вы получили 10 дополнительных печений! (Шанс: 1%)")

    wheat_chance = 50 - 5 * level
    if random.randint(1, 100) <= wheat_chance:
        resources[1] += 1
        messages.append(f"Вы получили 1 пшеницу! (Шанс: {wheat_chance}%)")

    cocoa_chance = 5
    if random.randint(1, 100) <= cocoa_chance:
        resources[0] += 1
        messages.append(f"Вы получили 1 какао-боб! (Шанс: {cocoa_chance}%)")

    if 2 <= level <= 5:
        diamond_chance = 30 - 5 * level
        if random.randint(1, 100) <= diamond_chance:
            resources[3] += 1
            messages.append(f"Вы получили 1 алмаз! (Шанс: {diamond_chance}%)")

    if 1 <= level <= 10:
        emerald_chance = 3
        if random.randint(1, 100) <= emerald_chance:
            resources[5] += 1
            messages.append(f"Вы получили 1 изумруд! (Шанс: {emerald_chance}%)")

    user_balances["ресурсы"] = "/".join(map(str, resources))
    user_balances["последний фарм"] = datetime.now().strftime("%H:%M %d-%m-%Y")
    balances[username] = user_balances
    save_balances(balances)

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

    match = re.match(r'^дать\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?', text, re.IGNORECASE)
    if not match:
        await msg.reply_text("Неверный формат. Используйте: дать <количество> [название валюты]")
        return

    amount = int(match.group(1))
    currency_text = match.group(2)

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
        await msg.reply_text("Нельзя переводить себе !")
        return

    balances = load_balances()
    sender_balances = balances.get(sender, {curr: 0 for curr in CURRENCIES})

    if sender_balances.get(currency, 0) < amount:
        await msg.reply_text(f"Кажется в мешочке не хватает {currency}.")
        return

    sender_balances[currency] = sender_balances.get(currency, 0) - amount
    balances[sender] = sender_balances

    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    recipient_balances[currency] = recipient_balances.get(currency, 0) + amount
    balances[recipient] = recipient_balances

    save_balances(balances)



    moscow_tz = timezone(timedelta(hours=3))

    try:
        log_transaction({
            "timestamp": datetime.now(moscow_tz).isoformat(),
            "type": "дать",
            "from": str(sender),
            "to": str(recipient),
            "currency": currency,
            "amount": amount
        })
    except Exception:
        pass  # Ошибка при логировании — продолжаем без лога

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
    balances = load_balances()
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    recipient_balances[currency] = recipient_balances.get(currency, 0) + amount
    balances[recipient] = recipient_balances

    save_balances(balances)

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
    balances = load_balances()
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    current = recipient_balances.get(currency, 0)
    recipient_balances[currency] = max(0, current - amount)
    balances[recipient] = recipient_balances

    save_balances(balances)

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
excluded_users_Admin = {"@hto_i_taki", "@Eparocheck"}  # исключить полностью

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
        await msg.reply_text("В твоём мешочке с Печеньками не хватает :(")
        return

    # Вычитаем печеньки
    balances.setdefault(username, {}).setdefault("печеньки", 0)
    balances[username]["печеньки"] -= count
    save_balances(balances)

    # Загрузка текущих билетов
    lottery = safe_load_lottery()
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
    save_lottery(updated_lottery)

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
        pass  # Ошибку лога игнорируем

    try:
        if random.randint(1,100)<chanse_N:
            await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪 ай молодец, держи промо: "+ PROMO)
        else:
            await msg.reply_text(f"{username} купил билеты за {count} печенек 🍪 ай молодец")
    except:
        pass  # Даже если не ответили — это не критично


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
def update_user_resources(username, balances, resources):
    resources_str = '/'.join(map(str, resources))
    if username not in balances:
        balances[username] = {}
    balances[username]["ресурсы"] = resources_str
    save_balances(balances)
async def handle_give_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    # Унифицированная обработка: приведём к нижнему регистру для сравнения
    if not text.lower().startswith("рес дать"):
        await msg.reply_text("Команда должна начинаться с 'рес дать'.")
        return

    # Удалим только самое первое вхождение 'рес дать' (в любом регистре)
    command = re.sub(r'^рес\s+дать', '', text, flags=re.IGNORECASE).strip()

    # Ожидается: <кол-во> <код_ресурса> [@username или ответ]
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

    # Пытаемся найти @username
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

    balances = load_balances()

    if sender not in balances or recipient not in balances:
        await msg.reply_text("Один из участников не зарегистрирован.")
        return

    sender_resources = get_user_resources(sender, balances)
    recipient_resources = get_user_resources(recipient, balances)

    resource_index = list(RESOURCES.keys()).index(resource_short)
    sender_level = balances[sender].get("уровень", 1)
    recipient_level = balances[recipient].get("уровень", 1)

    sender_limit = RESOURCE_LIMITS[resource_short](sender_level)
    recipient_limit = RESOURCE_LIMITS[resource_short](recipient_level)

    if sender_resources[resource_index] < amount:
        await msg.reply_text(f"У тебя не хватает {resource_name}.")
        return

    if recipient_resources[resource_index] + amount > recipient_limit:
        await msg.reply_text(f"У {recipient} нет места для {amount} {resource_name}.")
        return

    # Передаём ресурсы
    sender_resources[resource_index] -= amount
    recipient_resources[resource_index] += amount

    update_user_resources(sender, balances, sender_resources)
    update_user_resources(recipient, balances, recipient_resources)

    save_balances(balances)

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
        pass  # лог не должен ломать выполнение

    await msg.reply_text(f"{sender} перевёл {amount} {resource_name} {recipient}.")





async def handle_give_admin_resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.username != ADMIN_USERNAME:
        return

    text = msg.text.strip()

    # Удаляем префикс "рес дар" (в любом регистре и с пробелами)
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

    # Пытаемся найти @username
    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя через @username или ответом на сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()

    if recipient not in balances:
        await msg.reply_text("Получатель не зарегистрирован.")
        return

    recipient_resources = get_user_resources(recipient, balances)
    recipient_level = balances[recipient].get("уровень", 1)

    resource_index = list(RESOURCES.keys()).index(resource_short)
    recipient_limit = RESOURCE_LIMITS[resource_short](recipient_level)

    if recipient_resources[resource_index] + amount > recipient_limit:
        await msg.reply_text(f"У {recipient} нет места для {amount} {resource_name}.")
        return

    recipient_resources[resource_index] += amount
    update_user_resources(recipient, balances, recipient_resources)
    save_balances(balances)

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

    # Удаляем префикс "рес отнять" (с учетом регистра и пробелов)
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

    # Получатель: @username или ответ на сообщение
    recipient_match = re.search(r'@(\w+)', command)
    if recipient_match:
        recipient_tag = recipient_match.group(1)
    elif msg.reply_to_message and msg.reply_to_message.from_user.username:
        recipient_tag = msg.reply_to_message.from_user.username

    if not recipient_tag:
        await msg.reply_text("Укажи получателя через @username или ответом на сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()

    if recipient not in balances:
        await msg.reply_text("Получатель не зарегистрирован.")
        return

    recipient_resources = get_user_resources(recipient, balances)
    resource_index = list(RESOURCES.keys()).index(resource_short)

    if recipient_resources[resource_index] < amount:
        await msg.reply_text(f"У {recipient} нет {amount} {resource_name} для изъятия.")
        return

    recipient_resources[resource_index] -= amount
    update_user_resources(recipient, balances, recipient_resources)
    save_balances(balances)

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

    # Нормализация типа
    if "золот" in craft_raw or craft_raw == "золото":
        craft_type = "золотая печенька"
    else:
        craft_type = "печенька"

    username = get_username_from_message(msg)
    if not username:
        await msg.reply_text("Ошибка: не удалось определить пользователя.")
        return

    balances = load_balances()
    user_balances = balances.get(username)
    if user_balances is None:
        await msg.reply_text("Вы не зарегистрированы. Напишите Баланс для начала.")
        return

    resources_str = user_balances.get("ресурсы", "0/0/0/0/0/0/0")
    try:
        resources = list(map(int, resources_str.split('/')))
    except ValueError:
        await msg.reply_text("Ошибка чтения ресурсов. Обратитесь к администратору.")
        return

    # Индексы ресурсов
    try:
        wheat_index = list(RESOURCES.keys()).index("п")
        cocoa_index = list(RESOURCES.keys()).index("к")
        cookie_index = list(RESOURCES.keys()).index("печенька")
        gold_cookie_index = list(RESOURCES.keys()).index("р")
    except ValueError:
        await msg.reply_text("Ошибка конфигурации ресурсов.")
        return

    if craft_type == "печенька":
        required_wheat = 2 * amount
        required_cocoa = 1 * amount

        if resources[wheat_index] < required_wheat or resources[cocoa_index] < required_cocoa:
            await msg.reply_text(f"Не хватает ресурсов для крафта {amount} обычных печенек.")
            return

        resources[wheat_index] -= required_wheat
        resources[cocoa_index] -= required_cocoa
        resources[cookie_index] += amount

        try:
            log_transaction({
                "timestamp": datetime.now(moscow_tz).isoformat(),
                "type": "крафт",
                "username": username,
                "resource": "печенька",
                "amount": amount
            })
        except:
            pass

        await msg.reply_text(f"Вы скрафтили {amount} обычных печенек.")

    elif craft_type == "золотая печенька":
        required_wheat = 2 * amount
        required_cocoa = 1 * amount
        required_cookies = 1 * amount

        if (
            resources[wheat_index] < required_wheat or
            resources[cocoa_index] < required_cocoa or
            resources[cookie_index] < required_cookies
        ):
            await msg.reply_text(f"Не хватает ресурсов для крафта {amount} золотых печенек.")
            return

        resources[wheat_index] -= required_wheat
        resources[cocoa_index] -= required_cocoa
        resources[cookie_index] -= required_cookies
        resources[gold_cookie_index] += amount

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

        await msg.reply_text(f"Вы скрафтили {amount} золотых печенек.")

    else:
        await msg.reply_text("Неизвестный тип. Пример: крафт 1 печенька / крафт 1 золотая печенька")
        return

    # Обновление и сохранение
    user_balances["ресурсы"] = "/".join(map(str, resources))
    balances[username] = user_balances
    save_balances(balances)
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
ULTRAHELP_INFO = """🔮 *УльтХелп — Ультемативная Помощь от Создателя*

Позволяет расширить функциональность вашей механики (механика — это ваша идея/бизнес по заработку Печенек и т.п.).
УльтХелпы продаются за Печеньки. Каждый игрок может придумать свою механику (например, своё казино).

⚠️ *Предупреждение:* Прочитайте все УльтХелпы, чтобы случайно не потерять Печеньки!

---

🎰 *УльтХелп: Эмодзи Казино*
👤 Владелец: Gaster999  
📜 Описание:  
При использовании его эмодзи Казино вы автоматически участвуете в его казино.

💸 *Условия казино от Gaster999:*  
• Стоимость игры: 1 Печенька  
• Приз за 3 в ряд: 5 Печенек  
🎮 Для игры переведите по 1 Печеньке за игру Gaster999 командой `дать 1` (с указанием на его сообщение или допишите его тег в конце) и киньте эмодзи казино.

---

🎲 *УльтХелп: Эмодзи Кубик*
👤 Владелец: Shittttt  
📜 Описание:  
При использовании его эмодзи Кубик вы автоматически участвуете в его игре *Покер*.
"""
SHOP_KEYWORDS = [
    "магазин", "зачем нужны печеньки", "зачем нужны печенья",
    "куда тратить печеньки", "что делать с печеньками", "на что потратить печеньки",
    "можно ли купить", "продажа", "покупка", "как использовать печеньки",
    "обменять печеньки", "награды за печеньки"
]
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
    elif lower_text in ["казино", "эмодзи", "ультхелп", "ультхелпы", "помощь"]:
        await update.message.reply_text(ULTRAHELP_INFO, parse_mode="Markdown")
    elif lower_text in ["окак", "о как"]:
        await update.message.reply_text("отак", parse_mode="Markdown")
    elif any(keyword in lower_text for keyword in SHOP_KEYWORDS):
        await update.message.reply_text(SHOP_INFO, parse_mode="Markdown")
    elif any(keyword in lower_text for keyword in ["котик", "кот", "киса", "кошак", "котя", "котёнок"]):
        await update.message.reply_text("Я хороший Котик!", parse_mode="Markdown")

    elif random.randint(1,100)<=chanse_vezde:
        await update.message.reply_text(f"Ты мне понравился, держи промо: {PROMO}")

PROMO = "i love @catcookie_bot"# ✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅ПРОМОКОД✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
chanse_N = 40
chanse_balance = 0
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
    "🛍️ магазин": "Показать, что можно купить за печеньки, ресурсы"
}

UPDATE_LOG = """
📦 Последние обновления 🛠:

✅ Добавлены две особые и самые важные команды
✅ Добавлена команда "Магазин"
✅ Бот реагирует на "казино", "эмодзи", "ультхелп", "ультхелпы", "помощь" и выводит команду "ультхелп"
✅ Добавлена команда "Ресурсы" для объяснения 
✅ Обновлена команда "Уровень"
✅ Исправлена команда крафт
✅ Исправлена выдача железа
✅ Обновлены все фразы бота
✅ Добавлено условие для перехода на 11-й Уровень(на каждые 10 уровней)
✅ Максимальный Уровень прописан до 20-го
✅ Добавлены бонусы в команде "Хочу Печеньки"
✅ Добавлена команда крафт <количество> <печеньки|золотых печеньек> 
✅ Добавлена Пшеница, Какао-бобы, железо, золото, алмазы, изумруды ️
 Добавлена доп защита от отката в билетах ️
 Обновлена  фраза  в балансе ️
 Исправлена команда "N <число>" — покупка билетов 🎟️
 Команда "баланс" теперь показывает количество билетов
 Исправлена ошибка с покупкой 1 билета
 Оптимизирована функция сохранения лотереи
"""


async def handle_level_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("levels_price.json", "r", encoding="utf-8") as f:
            prices = json.load(f)
    except FileNotFoundError:
        prices = {}

    lines = [
        "📊 *Уровни*",
        "Уровень увеличивает фарм печенек и открывает новые возможности. "
        "_Для прокачки высоких уровней потребуются ресурсы._\n"
    ]

    for level in range(1, 21):
        min_amt, max_amt, chances = level_config[level]
        chance_str = "/".join(f"{round(p * 100)}" for p in chances)
        price = prices.get(str(level), "🚫" if level == 1 else "неизвестно")
        lines.append(f"*{level} ур*: {min_amt}–{max_amt} 🍪 в день | шанс: {chance_str}% | цена: {price}")

    lines.append("\n📉 *Откуп от поражения*")
    lines.append("Доступен при достижении нужного уровня. Цена — в 2 раза ниже.\n")
    lines.append("*Формат:* `(Ступень — Этап) : Уровень`")
    lines.append("""
📌 *Подготовка*
- 1 ст. : 2 ур
- 2 ст. : 4 ур
- 3 ст. : 6 ур
- Финал ПЭ : 8 ур

📌 *Основной этап*
- 1 этап : 10 ур
- 2 этап : 12 ур
- 3 этап : 14 ур
- Финал : 🚫 откуп недоступен
""")



    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
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
📩 Для покупки пишите *Адину* — `@hto_i_taki` (Ягами)
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
if __name__ == '__main__':
    threading.Thread(target=start_dummy_server).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Бот запущен...")
    app.run_polling()
