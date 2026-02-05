import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pycoingecko import CoinGeckoAPI
import openai
from openai import OpenAI

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_TOKEN not found")
    exit(1)

openai.api_key = OPENAI_API_KEY

# Initialize CoinGecko
cg = CoinGeckoAPI()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Cyntel AI 🚀\n\n"
        "Available commands:\n"
        "/price <ticker> — get current price & 24h change\n"
        "/scan <ticker> — deep analysis with AI insights\n"
        "/help — show this message\n\n"
        "Example: /price bitcoin or /scan ethereum"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a ticker.\nExample: /price bitcoin")
        return

    ticker = context.args[0].lower()
    try:
        data = cg.get_price(ids=ticker, vs_currencies='usd', include_24hr_change='true', include_market_cap='true')
        if ticker not in data:
            await update.message.reply_text(f"❌ Could not find {ticker.upper()}. Try 'bitcoin', 'ethereum', 'solana', etc.")
            return

        info = data[ticker]
        price = info['usd']
        change_24h = info.get('usd_24h_change', 0)
        market_cap = info.get('usd_market_cap', 'N/A')

        change_emoji = "🟢" if change_24h > 0 else "🔴" if change_24h < 0 else "⚪"

        message = (
            f"📊 {ticker.upper()}\n\n"
            f"💰 Price: ${price:,.2f}\n"
            f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
            f"🧢 Market Cap: ${market_cap:,.0f}" if market_cap != 'N/A' else f"🧢 Market Cap: N/A"
        )
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error fetching data: {str(e)}")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a ticker.\nExample: /scan bitcoin")
        return

    ticker = context.args[0].lower()
    await update.message.reply_text("🔍 Analyzing... (this may take 5–10 seconds)")

    try:
        # Get detailed market data
        coin_data = cg.get_coins_markets(vs_currency='usd', ids=ticker)
        if not coin_data:
            await update.message.reply_text(f"❌ No data found for {ticker.upper()}")
            return

        coin = coin_data[0]
        price = coin['current_price']
        change_24h = coin['price_change_percentage_24h']
        volume = coin['total_volume']
        market_cap = coin['market_cap']
        rank = coin['market_cap_rank']

        # Build prompt for OpenAI
        prompt = f"""
        Analyze this cryptocurrency objectively and analytically:
        - Current price: ${price:,.2f}
        - 24h price change: {change_24h:+.2f}%
        - Market cap rank: #{rank}
        - 24h trading volume: ${volume:,.0f}
        - Market cap: ${market_cap:,.0f}

        Give a short, direct assessment (2–4 sentences). Be analytical. Include slight cynicism if the data shows red flags (e.g. low volume, extreme pump/dump). Do not shill or hype.
        """

        # Modern OpenAI 1.x syntax
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )

        analysis = response.choices[0].message.content.strip()

        message = (
            f"🧠 Cyntel AI Analysis — {ticker.upper()}\n\n"
            f"💰 ${price:,.2f}   |   {change_24h:+.2f}% (24h)\n"
            f"📊 Rank #{rank}   |   Volume ${volume:,.0f}\n\n"
            f"{analysis}"
        )

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"⚠️ AI analysis failed: {str(e)}")

def main():
    print("Starting Cyntel AI bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("help", start))

    print("Bot is online and ready!")
    app.run_polling()

if __name__ == "__main__":
    main()