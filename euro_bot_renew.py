# euro_bot_renew.py

import os
import json
import logging
import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === Налаштування ===
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
MINFIN_TOKEN = os.getenv("MINFIN_TOKEN")
LAST_RATE_FILE = "last_rate.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Джерела обміну ===

async def get_from_privat(currency: str) -> dict | None:
    try:
        url = "https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                for item in data:
                    if item["ccy"] == currency.upper():
                        return {
                            "bank": "ПриватБанк",
                            "buy": item["buy"],
                            "sell": item["sale"]
                        }
    except Exception as e:
        logger.warning(f"Privat error: {e}")
    return None

async def get_from_minfin(currency: str) -> list:
    try:
        url = f"https://api.minfin.com.ua/fb/currency/list?currency={currency}&apiKey={MINFIN_TOKEN}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return [
                    {
                        "bank": item["bank"],
                        "buy": item["bid"],
                        "sell": item["ask"]
                    }
                    for item in data
                    if item.get("bid") not in ("0.00", None) and item.get("ask") not in ("0.00", None)
                ]
    except Exception as e:
        logger.warning(f"Minfin error: {e}")
    return []

async def get_from_binance(currency: str) -> dict | None:
    try:
        symbol = f"{currency.upper()}UAH"
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if "price" in data:
                    return {
                        "bank": "Binance",
                        "buy": data["price"],
                        "sell": data["price"]
                    }
    except Exception as e:
        logger.warning(f"Binance error: {e}")
    return None

async def get_from_monobank(currency: str) -> dict | None:
    try:
        code_map = {"USD": 840, "EUR": 978, "PLN": 985}
        code = code_map.get(currency.upper())
        if not code:
            return None
        url = "https://api.monobank.ua/bank/currency"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                for item in data:
                    if item.get("currencyCodeA") == code and item.get("currencyCodeB") == 980:
                        return {
                            "bank": "Monobank",
                            "buy": str(round(item["rateBuy"], 2)),
                            "sell": str(round(item["rateSell"], 2))
                        }
    except Exception as e:
        logger.warning(f"Monobank error: {e}")
    return None

# === Агрегація курсів ===

async def get_all_rates(currency: str) -> list:
    sources = [get_from_minfin, get_from_privat, get_from_binance, get_from_monobank]
    rates = []
    for source in sources:
        result = await source(currency)
        if isinstance(result, list):
            rates.extend(result)
        elif isinstance(result, dict):
            rates.append(result)
    return rates

async def get_exchange_rate(currency: str) -> str:
    rates = await get_all_rates(currency)
    if not rates:
        return f"❌ Курс для {currency} не знайдено."
    rate = rates[0]
    return f"*{currency}* ({rate['bank']}):\nКупівля: `{rate['buy']}`\nПродаж: `{rate['sell']}`"

# === Збереження курсу ===

def save_last_rate(currency: str, rate: float):
    data = {}
    if os.path.exists(LAST_RATE_FILE):
        try:
            with open(LAST_RATE_FILE, "r") as f:
                data = json.load(f)
        except:
            pass
    data[currency] = rate
    with open(LAST_RATE_FILE, "w") as f:
        json.dump(data, f)

def load_last_rate(currency: str) -> float | None:
    if not os.path.exists(LAST_RATE_FILE):
        return None
    with open(LAST_RATE_FILE, "r") as f:
        data = json.load(f)
    return float(data.get(currency)) if currency in data else None

# === Telegram-команди ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Вітаю! Бот надсилає курс щодня о 9:00 та щопонеділка зведення.\n"
        "Команди:\n/seteur\n/setusd\n/setpln\n/price\n/bestprice\n/allrates"
    )

async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE, val: str):
    context.bot_data["currency"] = val
    await update.message.reply_text(f"✅ Валюта змінена на {val}")

async def set_eur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_currency(update, context, "EUR")

async def set_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_currency(update, context, "USD")

async def set_pln(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_currency(update, context, "PLN")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = context.bot_data.get("currency", "EUR")
    text = await get_exchange_rate(currency)
    await update.message.reply_text(text, parse_mode="Markdown")

async def bestprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = context.bot_data.get("currency", "EUR")
    rates = await get_all_rates(currency)
    if not rates:
        await update.message.reply_text("❌ Немає доступних курсів.")
        return
    top_rates = sorted(rates, key=lambda x: float(x["sell"]))[:3]
    text = f"💰 *Найкращі курси продажу {currency}:*\n"
    for r in top_rates:
        text += f"\n*{r['bank']}*\nКупівля: `{r['buy']}`\nПродаж: `{r['sell']}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def allrates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = context.bot_data.get("currency", "EUR")
    rates = await get_all_rates(currency)
    if not rates:
        await update.message.reply_text("❌ Немає даних по валюті.")
        return
    seen = set()
    text = f"📋 *Курси {currency} по банках:*\n"
    for r in sorted(rates, key=lambda x: x["bank"]):
        if r["bank"] not in seen:
            seen.add(r["bank"])
            text += f"\n*{r['bank']}*\nКупівля: `{r['buy']}`\nПродаж: `{r['sell']}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# === Автосповіщення ===

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
        percent
        
        
        
import asyncio

if __name__ == "__main__":
    logging.info("🚦 Запуск run_polling — бот слухає Telegram")

    async def main():
    app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("seteur", set_eur))
        app.add_handler(CommandHandler("setusd", set_usd))
        app.add_handler(CommandHandler("setpln", set_pln))
        app.add_handler(CommandHandler("price", price))
        app.add_handler(CommandHandler("bestprice", bestprice))
        app.add_handler(CommandHandler("allrates", allrates))

        # Планувальник у поточному loop
        loop = asyncio.get_running_loop()
        scheduler = AsyncIOScheduler(event_loop=loop)
        scheduler.add_job(send_weekly_update, trigger="cron", day_of_week="mon", hour=9, args=[app])
        scheduler.add_job(check_rate_spike, trigger="cron", hour=9, args=[app])
        scheduler.start()

        await app.run_polling()

    asyncio.run(main())