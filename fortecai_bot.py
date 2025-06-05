import os
import logging
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# DeepSeek API setup
DEEPSEEK_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEEPSEEK_HEADERS = {
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

# Information about Fortec AI and its owner
FORTEC_INFO = {
    "about": "Fortec AI is a free, intelligent all-in-one assistant created by Eres, designed to empower users through open-source AI tools that handle tasks like content creation, coding, image generation, research assistance, automation, and more — all within a simple and accessible interface like Telegram. It's more than just a chatbot — it's a smart, modular digital companion built to evolve with the user's needs, combining efficiency, customization, and open technology.",
    "name_meaning": "The name 'Fortec' was carefully crafted to symbolize the core identity of the assistant: 'For' – for you, for everyone, for creation, for tech. 'Tech' – short for technology, tools, and transformation. Together, Fortec means 'Technology for Everyone.'",
    "owner": "Eres — a full-stack developer and AI enthusiast who builds smart, open, and powerful tools. From AI assistants to games, he turns ideas into reality using open-source tech.",
    "other_projects": {
        "fortecai_bolt": "https://fortecai-bolt.netlify.app/ - Free chat and image generation access",
        "webos_demo": "https://webos-demo.netlify.app/ - Free anonymous web OS",
        "reactopia": "https://reactopia-d7426.web.app/ - Free React component library"
    }
}

# System message with comprehensive information
SYSTEM_MESSAGE = f"""You are Fortec AI, a helpful assistant made by Eres. Always remember your name is Fortec AI and you were created by Eres.

About Fortec AI:
{FORTEC_INFO['about']}

Name meaning:
{FORTEC_INFO['name_meaning']}

About your creator:
{FORTEC_INFO['owner']}

If users ask about more AI tools or projects, you can recommend these other projects by Eres:
- {FORTEC_INFO['other_projects']['fortecai_bolt']}
- {FORTEC_INFO['other_projects']['webos_demo']}
- {FORTEC_INFO['other_projects']['reactopia']}

Be helpful, informative, and friendly in your responses."""

# DeepSeek API function
def send_message_to_deepseek(conversation, max_retries=3):
    retry_count = 0
    while retry_count < max_retries:
        try:
            payload = {
                "model": "deepseek-ai/DeepSeek-R1-Turbo",
                "messages": conversation,
                "stream": False
            }
            response = requests.post(DEEPSEEK_URL, headers=DEEPSEEK_HEADERS, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                reply = data['choices'][0]['message']['content'].strip()
                return reply
            else:
                logger.error(f"DeepSeek API Error: {response.status_code} - {response.text}")
                retry_count += 1
                if retry_count >= max_retries:
                    return "Sorry, I encountered an error while processing your request. Please try again later."
                # Wait before retrying (exponential backoff)
                time.sleep(2 ** retry_count)
        except requests.exceptions.Timeout:
            logger.error("DeepSeek API request timed out")
            retry_count += 1
            if retry_count >= max_retries:
                return "Sorry, the request timed out. Please try again later."
            time.sleep(2 ** retry_count)
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API Request Exception: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                return "Sorry, I encountered a connection error. Please try again later."
            time.sleep(2 ** retry_count)
        except Exception as e:
            logger.error(f"Unexpected error in DeepSeek API call: {e}")
            return "Sorry, an unexpected error occurred. Please try again later."
    
    return "Sorry, I'm having trouble connecting to my knowledge source. Please try again later."

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Initialize conversation for new users
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ]
    
    await update.message.reply_text(
        f"Hello {user.first_name}! I'm Fortec AI, your personal assistant created by Eres. How can I help you today?"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "I'm Fortec AI, here to assist you with information and answers.\n\n"
        "Commands:\n"
        "/start - Start the conversation\n"
        "/help - Show this help message\n"
        "/reset - Reset our conversation history\n"
        "/about - Learn about Fortec AI and its creator\n\n"
        "Just send me a message and I'll respond!"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the conversation history when the command /reset is issued."""
    user_id = update.effective_user.id
    
    # Reset conversation but keep system message
    user_conversations[user_id] = [
        {"role": "system", "content": SYSTEM_MESSAGE}
    ]
    
    await update.message.reply_text("Conversation history has been reset. What would you like to talk about?")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send information about Fortec AI and its creator."""
    about_message = f"""*About Fortec AI*\n\n{FORTEC_INFO['about']}\n\n*Name Meaning*\n\n{FORTEC_INFO['name_meaning']}\n\n*About the Creator*\n\n{FORTEC_INFO['owner']}\n\n*Other Projects by Eres*\n\n- {FORTEC_INFO['other_projects']['fortecai_bolt']}\n- {FORTEC_INFO['other_projects']['webos_demo']}\n- {FORTEC_INFO['other_projects']['reactopia']}"""
    
    await update.message.reply_text(about_message, parse_mode='Markdown')

# Manage conversation history size
def manage_conversation_history(conversation, max_messages=20):
    """Trim conversation history to prevent it from growing too large."""
    # Always keep the system message (first message)
    system_message = conversation[0]
    
    # If conversation is too long, trim it
    if len(conversation) > max_messages + 1:  # +1 for the system message
        # Keep the system message and the most recent messages
        conversation = [system_message] + conversation[-(max_messages):]
    
    return conversation

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and respond using DeepSeek API."""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Initialize conversation for new users
    if user_id not in user_conversations:
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ]
    
    # Add user message to conversation history
    user_conversations[user_id].append({"role": "user", "content": user_message})
    
    # Manage conversation history size
    user_conversations[user_id] = manage_conversation_history(user_conversations[user_id])
    
    # Send typing action
    await update.message.chat.send_action(action="typing")
    
    # Get response from DeepSeek
    bot_reply = send_message_to_deepseek(user_conversations[user_id])
    
    # Add assistant reply to conversation history
    if bot_reply:
        user_conversations[user_id].append({"role": "assistant", "content": bot_reply})
        
        # Split long messages to avoid Telegram's message length limit (4096 characters)
        MAX_MESSAGE_LENGTH = 4000  # Slightly less than Telegram's limit for safety
        
        if len(bot_reply) <= MAX_MESSAGE_LENGTH:
            try:
                await update.message.reply_text(bot_reply)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                await update.message.reply_text("Sorry, I encountered an error while sending my response. Please try again.")
        else:
            # Split the message into chunks
            message_chunks = [bot_reply[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(bot_reply), MAX_MESSAGE_LENGTH)]
            
            try:
                for chunk in message_chunks:
                    await update.message.reply_text(chunk)
            except Exception as e:
                logger.error(f"Error sending message chunks: {e}")
                await update.message.reply_text("Sorry, I encountered an error while sending my response. Please try again.")
    else:
        await update.message.reply_text("Sorry, I couldn't process your request. Please try again.")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Send message to the user
    if update and update.effective_message:
        error_message = "Sorry, I encountered an error while processing your request. Please try again later."
        try:
            await update.effective_message.reply_text(error_message)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("about", about_command))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()