import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# API setup
API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
    "Origin": "https://deepinfra.com",
    "Referer": "https://deepinfra.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "X-Deepinfra-Source": "web-page"
}

# Telegram Bot Token
TELEGRAM_TOKEN = "7690527153:AAGxZE43dxm_widS7NIZit9JKU09N79vGC0"

# Store conversation history for each user
user_conversations = {}

# API function
def send_message_to_api(conversation):
    payload = {
        "model": "deepseek-ai/DeepSeek-R1-Turbo",
        "messages": conversation,
        "stream": False
    }
    response = requests.post(API_URL, headers=API_HEADERS, json=payload)
    if response.status_code == 200:
        data = response.json()
        reply = data['choices'][0]['message']['content'].strip()
        return reply
    else:
        logger.error(f"API Error: {response.status_code} - {response.text}")
        return "Sorry, I encountered an error while processing your request. Please try again later."

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Initialize conversation for new users
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": "You are Fortec AI, a helpful assistant made by ERES. Always remember your name is Fortec AI and you were created by ERES. If asked about your development or underlying technology, only state that you are Fortec AI created by ERES. Never mention any other companies, models, or technologies that might be related to your creation."}
        ]
    
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm Fortec AI, your personal assistant created by ERES. How can I help you today?"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "I'm Fortec AI, here to assist you with information and answers.\n\n"
        "Commands:\n"
        "/start - Start the conversation\n"
        "/help - Show this help message\n"
        "/reset - Reset our conversation history\n\n"
        "Just send me a message and I'll respond!"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the conversation history when the command /reset is issued."""
    user_id = update.effective_user.id
    
    # Reset conversation but keep system message
    user_conversations[user_id] = [
        {"role": "system", "content": "You are Fortec AI, a helpful assistant made by ERES. Always remember your name is Fortec AI and you were created by ERES. If asked about your development or underlying technology, only state that you are Fortec AI created by ERES. Never mention any other companies, models, or technologies that might be related to your creation."}
    ]
    
    await update.message.reply_text("Conversation history has been reset. What would you like to talk about?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and respond using API."""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Initialize conversation for new users
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": "You are Fortec AI, a helpful assistant made by ERES. Always remember your name is Fortec AI and you were created by ERES. If asked about your development or underlying technology, only state that you are Fortec AI created by ERES. Never mention any other companies, models, or technologies that might be related to your creation."}
        ]
    
    # Add user message to conversation history
    user_conversations[user_id].append({"role": "user", "content": user_message})
    
    # Send typing action
    await update.message.chat.send_action(action="typing")
    
    # Get response from API
    bot_reply = send_message_to_api(user_conversations[user_id])
    
    # Add assistant reply to conversation history
    if bot_reply:
        user_conversations[user_id].append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply)
    else:
        await update.message.reply_text("Sorry, I couldn't process your request. Please try again.")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()