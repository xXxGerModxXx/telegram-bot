import os
import json
import re
from quart import Quart, request
from telegram import Update, Message
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TOKEN = "7604409638:AAFRrmzPflnsGj_a7q2fMd99w3x_GuNJ78c"
BALANCE_FILE = 'balances.json'

CURRENCIES = {
    "печеньки": "🍪",
    "трилистники": "☘️",
    "четырёхлистники": "🍀"
}

app = Quart(__name__)
application = ApplicationBuilder().token(TOKEN).build()

# ---- Функции для работы с балансом ----

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

# ---- Обработчики команд ----

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = get_username_from_message(update.message)
    balances = load_balances()
    user_balances = balances.get(username, {curr: 0 for curr in CURRENCIES})
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
        recipient_tag = f"@{recipient_match.group(1)}"
    elif msg.reply_to_message:
        recipient_tag = get_username_from_message(msg.reply_to_message)

    if not recipient_tag:
        await msg.reply_text("Не найден получатель.")
        return

    sender = get_username_from_message(msg)
    if sender == recipient_tag:
        await msg.reply_text("Нельзя передавать валюту самому себе.")
        return

    balances = load_balances()
    balances.setdefault(recipient_tag, {}).setdefault(currency, 0)
    balances[recipient_tag][currency] += amount
    save_balances(balances)

    await msg.reply_text(f"{sender} подарил {amount} {currency} {CURRENCIES[currency]} пользователю {recipient_tag}")

# ---- Регистрируем обработчики ----

application.add_handler(MessageHandler(filters.Regex(r'^баланс$'), handle_balance))
application.add_handler(MessageHandler(filters.Regex(r'^дать\s+\d+'), handle_give))

# ---- Webhook endpoints ----

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

# ---- Запуск сервера ----

if __name__ == "__main__":
    import asyncio
    port = int(os.environ.get("PORT", 10000))
    asyncio.run(application.initialize())
    app.run(host="0.0.0.0", port=port)
