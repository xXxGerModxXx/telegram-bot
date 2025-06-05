import os
import json
import re
import logging
from quart import Quart, request
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

TOKEN = "7604409638:AAFRrmzPflnsGj_a7q2fMd99w3x_GuNJ78c"
BALANCE_FILE = 'balances.json'
ADMIN_USERNAME = "hto_i_taki"  # без @

CURRENCIES = {
    "печеньки": "🍪",
    "трилистники": "☘️",
    "четырёхлистники": "🍀"
}

app = Quart(__name__)
application = ApplicationBuilder().token(TOKEN).build()

# --- Работа с балансами ---

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

# --- Обработчики команд ---

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    balances = load_balances()
    user_balances = balances.get(username, {})
    if not user_balances:
        user_balances = {curr: 0 for curr in CURRENCIES}
    lines = [f"{username}, твой баланс:"]
    for curr, emoji in CURRENCIES.items():
        amount = user_balances.get(curr, 0)
        lines.append(f"{amount} {curr} {emoji}")
    await update.message.reply_text("\n".join(lines))

async def handle_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = msg.text.strip()

    match = re.match(r'^дать\s+(\d+)(?:\s+(печеньки|трилистника|трилистники|четырёхлистника|четырёхлистники))?', text, re.IGNORECASE)
    if not match:
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

    # Списываем у отправителя
    sender_balances[currency] -= amount
    balances[sender] = sender_balances

    # Начисляем получателю
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    recipient_balances[currency] += amount
    balances[recipient] = recipient_balances

    save_balances(balances)

    await msg.reply_text(f"{sender} перевёл {amount} {currency} {CURRENCIES[currency]} {recipient}.")

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
    recipient_balances[currency] += amount
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
        await msg.reply_text("Укажи пользователя или ответь на его сообщение.")
        return

    recipient = f"@{recipient_tag}"
    balances = load_balances()
    recipient_balances = balances.get(recipient, {curr: 0 for curr in CURRENCIES})
    if recipient_balances.get(currency, 0) < amount:
        await msg.reply_text(f"У пользователя недостаточно {currency} для списания.")
        return
    recipient_balances[currency] -= amount
    balances[recipient] = recipient_balances

    save_balances(balances)
    await msg.reply_text(f"У {recipient} отняли {amount} {currency} {CURRENCIES[currency]}")

# --- Регистрируем обработчики ---

application.add_handler(MessageHandler(filters.Regex(r'^баланс$'), handle_balance))
application.add_handler(MessageHandler(filters.Regex(r'^дать\s+\d+'), handle_give))
application.add_handler(MessageHandler(filters.Regex(r'^дар\s+\d+'), handle_give_admin))
application.add_handler(MessageHandler(filters.Regex(r'^отнять\s+\d+'), handle_take_admin))

# --- Webhook endpoints для Quart ---

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = await request.get_data(as_text=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"

@app.route("/", methods=["GET"])
async def index():
    webhook_url = f"https://telegram-bot-5uln.onrender.com/{TOKEN}"  # Замени на свой URL Render!
    await application.bot.set_webhook(webhook_url)
    return "Webhook установлен"

# --- Запуск сервера ---

if __name__ == "__main__":
    import asyncio
    port = int(os.environ.get("PORT", 10000))
    asyncio.run(application.initialize())
    app.run(host="0.0.0.0", port=port)
