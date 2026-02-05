import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pycoingecko import CoinGeckoAPI
from openai import OpenAI
from moralis import evm_api

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")  # Required for portfolio

if not TELEGRAM_TOKEN:
    print("ERROR: TELEGRAM_TOKEN not found")
    exit(1)

if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not found")
    exit(1)

if not MORALIS_API_KEY:
    print("ERROR: MORALIS_API_KEY not found — /portfolio will fail")
    # Don't exit here so the bot still runs, but warn

# Initialize CoinGecko
cg = CoinGeckoAPI()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Cyntel AI 🚀\n\n"
        "Available commands:\n"
        "/price <ticker> — get current price & 24h change\n"
        "/scan <ticker> — deep analysis with AI insights\n"
        "/portfolio <wallet> — track Base wallet holdings\n"
        "/help — show this message\n\n"
        "Example: /price bitcoin or /portfolio 0x1234...abcd"
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

        prompt = f"""
        Analyze this cryptocurrency objectively and analytically:
        - Current price: ${price:,.2f}
        - 24h price change: {change_24h:+.2f}%
        - Market cap rank: #{rank}
        - 24h trading volume: ${volume:,.0f}
        - Market cap: ${market_cap:,.0f}

        Give a short, direct assessment (2–4 sentences). Be analytical. Include slight cynicism if the data shows red flags (e.g. low volume, extreme pump/dump). Do not shill or hype.
        """

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

# ────────────────────────────────────────────────
# Portfolio function – correctly placed here (NOT indented inside scan)
async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a Base wallet address.\nExample: /portfolio 0x1234...abcd")
        return

    wallet = context.args[0].lower()
    await update.message.reply_text("📂 Fetching portfolio... (this may take 5–10 seconds)")

    try:
        params = {"chain": "base", "address": wallet}
        result = evm_api.token.get_wallet_token_balances(
            api_key=os.getenv("MORALIS_API_KEY"),
            params=params
        )

        if not result:
            await update.message.reply_text(f"❌ No tokens found for {wallet}")
            return

        total_value = 0
        holdings = []
        for token in result:
            if token['balance'] == 0:
                continue
            ticker = token['symbol'].lower()
            try:
                data = cg.get_price(ids=ticker, vs_currencies='usd')
                price = data.get(ticker, {}).get('usd', 0)
                value = (int(token['balance']) / 10**token['decimals']) * price
                total_value += value
                holdings.append({
                    'symbol': token['symbol'],
                    'amount': int(token['balance']) / 10**token['decimals'],
                    'value': value
                })
            except:
                pass  # Skip if price not found

        holdings.sort(key=lambda x: x['value'], reverse=True)

        prompt = f"Analyze this crypto portfolio: Total value ${total_value:,.2f}. Top holdings: {', '.join([f'{h['symbol']} (${h['value']:.2f})' for h in holdings[:5]])}. Give a short, direct assessment (2–4 sentences). Highlight risks like concentration or low liquidity."

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        analysis = response.choices[0].message.content.strip()

        message = (
            f"💼 Portfolio for {wallet[:6]}...{wallet[-4:]}\n\n"
            f"📈 Total Value: ${total_value:,.2f}\n\n"
            f"Top Holdings:\n" + "\n".join([f"- {h['symbol']}: {h['amount']:.4f} (${h['value']:.2f})" for h in holdings[:5]]) + "\n\n"
            f"🧠 AI Assessment:\n{analysis}"
        )

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Portfolio fetch failed: {str(e)}")

def main():
    print("Starting Cyntel AI bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("portfolio", portfolio))  # This line makes /portfolio work

    print("Bot is online and ready!")
    app.run_polling()

if __name__ == "__main__":
    main()