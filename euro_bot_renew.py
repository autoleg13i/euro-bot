import os
import json
import logging
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === Завантаження ENV ===
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
MINFIN_TOKEN = os.getenv("MINFIN_TOKEN")
LAST_RATE_FILE = "last_rate.json"

# === Логування ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Джерела обміну ===
# (усі async-функції залишаються без змін — як у тебе)

# … залишити тут блоки:
# get_from_privat, get_from_minfin, get_from_binance, get_from_monobank,
# get_all_rates, get_exchange_rate, save_last_rate, load_last_rate

# === Telegram-команди ===
# start, set_currency, set_eur, set_usd, set_pln, price, bestprice, allrates

# === Автоматичні сповіщення ===
async def send_weekly_update(app):
    currency = app.bot_data.get("currency", "EUR")
    text = await get_exchange_rate(currency)
    await app.bot.send_message(chat_id=CHAT_ID, text=f"📈 Щотижневий курс:\n{text}", parse_mode="Markdown")

async def check_rate_spike(app):
    currency = app.bot_data.get("currency", "EUR")
    rates = await get_all_rates(currency)
    if not rates:
        return
    current = float(rates[0]["sell"])
    previous = load_last_rate(currency)
    if previous is not None:
        diff = abs(current - previous)
        percent = (diff / previous) * 100
        if percent > 1.5:
            trend = "🔺 зросла" if current > previous else "🔻 знизилась"
            text = f"⚠️ *Курс {currency} {trend} на {percent:.2f}%!*\nБуло: `{previous}` → Стало: `{current}`"
            await app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="Markdown")
    save_last_rate(currency, current)

# === Старт бота (синхронна точка входу, без event loop) ===
if __name__ == "__main__":
    logger.info("🚀 Стартуємо бота…")
    app = ApplicationBuilder().token(TOKEN).build()

    # Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("seteur", set_eur))
    app.add_handler(CommandHandler("setusd", set_usd))
    app.add_handler(CommandHandler("setpln", set_pln))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("bestprice", bestprice))
    app.add_handler(CommandHandler("allrates", allrates))

    # Планувальник
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_weekly_update, trigger="cron", day_of_week="mon", hour=9, minute=0, args=[app])
    scheduler.add_job(check_rate_spike, trigger="cron", hour=9, minute=0, args=[app])
    scheduler.start()

    app.run_polling()