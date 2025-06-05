import os
import logging
import requests
import time
import json
import re
import traceback
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, BadRequest, TimedOut, NetworkError
from flask import Flask, request

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Flask app for webhook
app = Flask(__name__)

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

# Image Generation API setup
IMAGE_GEN_URL = "https://gptimg.onrender.com/v1/images/generations"
IMAGE_GEN_HEADERS = {
    "Content-Type": "application/json"
}

# Image generation keywords
IMAGE_KEYWORDS = [
    "create image", "generate image", "make image", "draw", "picture", "photo", 
    "illustration", "render", "visualize", "design image", "paint", "sketch", 
    "imagine", "show me", "create a picture", "generate a photo"
]

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

# Image Generation function
async def generate_image(prompt, n=1, size="1024x1024", is_enhance=True):
    try:
        # Request payload
        payload = {
            "prompt": prompt,
            "n": n,
            "size": size,
            "is_enhance": is_enhance,
            "response_format": "url"
        }
        
        # Send POST request
        logger.info(f"Generating image with prompt: {prompt}")
        response = requests.post(IMAGE_GEN_URL, data=json.dumps(payload), headers=IMAGE_GEN_HEADERS, timeout=60)
        
        # Handle response
        if response.status_code == 200:
            data = response.json()
            image_urls = data.get("data", [])
            return image_urls
        else:
            logger.error(f"Failed to generate image: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        logger.error("Image generation request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Image generation request exception: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in image generation: {e}")
        return None

# Check if message contains image generation request
def is_image_request(message):
    message = message.lower()
    for keyword in IMAGE_KEYWORDS:
        if keyword in message:
            return True
    return False

# Extract image prompt from message
def extract_image_prompt(message):
    message = message.lower()
    for keyword in IMAGE_KEYWORDS:
        if keyword in message:
            # Extract text after the keyword
            prompt = re.split(keyword, message, 1)[1].strip()
            if prompt:
                return prompt
    # If no specific prompt found after keywords, use the whole message
    return message

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    try:
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
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await safe_reply(update, "Sorry, I encountered an error. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    try:
        await update.message.reply_text(
            "I'm Fortec AI, here to assist you with information and answers.\n\n"
            "Commands:\n"
            "/start - Start the conversation\n"
            "/help - Show this help message\n"
            "/reset - Reset our conversation history\n"
            "/about - Learn about Fortec AI and its creator\n"
            "/image - Generate an image (e.g., /image a futuristic city at night)\n\n"
            "You can also ask me to generate images by using phrases like:\n"
            "• 'create image of...'\n"
            "• 'generate picture of...'\n"
            "• 'draw...'\n"
            "• 'show me...'\n\n"
            "Just send me a message and I'll respond!"
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await safe_reply(update, "Sorry, I encountered an error. Please try again.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset the conversation history when the command /reset is issued."""
    try:
        user_id = update.effective_user.id
        
        # Reset conversation but keep system message
        user_conversations[user_id] = [
            {"role": "system", "content": SYSTEM_MESSAGE}
        ]
        
        await update.message.reply_text("Conversation history has been reset. What would you like to talk about?")
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        await safe_reply(update, "Sorry, I encountered an error. Please try again.")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send information about Fortec AI and its creator."""
    try:
        about_message = f"""*About Fortec AI*\n\n{FORTEC_INFO['about']}\n\n*Name Meaning*\n\n{FORTEC_INFO['name_meaning']}\n\n*About the Creator*\n\n{FORTEC_INFO['owner']}\n\n*Other Projects by Eres*\n\n- {FORTEC_INFO['other_projects']['fortecai_bolt']}\n- {FORTEC_INFO['other_projects']['webos_demo']}\n- {FORTEC_INFO['other_projects']['reactopia']}"""
        
        await update.message.reply_text(about_message, parse_mode='Markdown')
    except BadRequest as e:
        logger.error(f"Markdown error in about command: {e}")
        # Try without markdown if there's a formatting issue
        plain_about_message = f"About Fortec AI\n\n{FORTEC_INFO['about']}\n\nName Meaning\n\n{FORTEC_INFO['name_meaning']}\n\nAbout the Creator\n\n{FORTEC_INFO['owner']}\n\nOther Projects by Eres\n\n- {FORTEC_INFO['other_projects']['fortecai_bolt']}\n- {FORTEC_INFO['other_projects']['webos_demo']}\n- {FORTEC_INFO['other_projects']['reactopia']}"
        await update.message.reply_text(plain_about_message)
    except Exception as e:
        logger.error(f"Error in about command: {e}")
        await safe_reply(update, "Sorry, I encountered an error. Please try again.")

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate an image based on the provided prompt."""
    try:
        # Get the prompt from the command arguments
        prompt = ' '.join(context.args)
        
        if not prompt:
            await update.message.reply_text("Please provide a description for the image you want to generate. For example: /image a beautiful sunset over mountains")
            return
        
        # Send waiting message
        waiting_message = await update.message.reply_text("🎨 Generating your image... This may take up to a minute.")
        
        # Generate the image
        image_urls = await generate_image(prompt)
        
        # Delete waiting message
        try:
            await waiting_message.delete()
        except Exception as e:
            logger.warning(f"Could not delete waiting message: {e}")
        
        if image_urls and len(image_urls) > 0:
            # Send success message with the image URL
            await update.message.reply_text(f"✅ Here's your generated image based on: '{prompt}'")
            for url in image_urls:
                try:
                    await update.message.reply_photo(url)
                except BadRequest as e:
                    logger.error(f"Failed to send image: {e}")
                    # Just send the URL without the error message
                    await update.message.reply_text(f"`{url}`")
        else:
            # Send error message
            await update.message.reply_text("❌ Sorry, I couldn't generate an image. Please try again with a different description.")
    except Exception as e:
        logger.error(f"Error in image command: {e}")
        await safe_reply(update, "Sorry, I encountered an error while generating the image. Please try again.")

# Manage conversation history size
def manage_conversation_history(conversation, max_messages=20):
    """Trim conversation history to prevent it from growing too large."""
    try:
        # Always keep the system message (first message)
        system_message = conversation[0]
        
        # If conversation is too long, trim it
        if len(conversation) > max_messages + 1:  # +1 for the system message
            # Keep the system message and the most recent messages
            conversation = [system_message] + conversation[-(max_messages):]
        
        return conversation
    except Exception as e:
        logger.error(f"Error managing conversation history: {e}")
        # Return original conversation if there's an error
        return conversation

# Safe reply function to handle exceptions when sending messages
async def safe_reply(update, text, parse_mode=None):
    """Safely send a reply message, handling exceptions."""
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(text, parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is too long" in str(e):
            # Split long messages
            MAX_LENGTH = 4000
            chunks = [text[i:i+MAX_LENGTH] for i in range(0, len(text), MAX_LENGTH)]
            for chunk in chunks:
                try:
                    await update.effective_message.reply_text(chunk, parse_mode=None)
                except Exception as inner_e:
                    logger.error(f"Failed to send message chunk: {inner_e}")
        elif parse_mode:
            # Try without parse_mode if there's a formatting issue
            try:
                await update.effective_message.reply_text(text, parse_mode=None)
            except Exception as inner_e:
                logger.error(f"Failed to send plain message: {inner_e}")
        else:
            logger.error(f"Failed to send message: {e}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and respond using DeepSeek API or generate images."""
    try:
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Initialize conversation for new users
        if user_id not in user_conversations:
            user_conversations[user_id] = [
                {"role": "system", "content": SYSTEM_MESSAGE}
            ]
        
        # Check if this is an image generation request
        if is_image_request(user_message):
            # Extract the image prompt
            prompt = extract_image_prompt(user_message)
            
            # Send waiting message
            waiting_message = await update.message.reply_text("🎨 Generating your image... This may take up to a minute.")
            
            # Generate the image
            image_urls = await generate_image(prompt)
            
            # Delete waiting message
            try:
                await waiting_message.delete()
            except Exception as e:
                logger.warning(f"Could not delete waiting message: {e}")
            
            if image_urls and len(image_urls) > 0:
                # Send success message with the image URL
                await update.message.reply_text(f"✅ Here's your generated image based on: '{prompt}'")
                for url in image_urls:
                    try:
                        await update.message.reply_photo(url)
                    except BadRequest as e:
                        logger.error(f"Failed to send image: {e}")
                        # Just send the URL without the error message
                        await update.message.reply_text(f"`{url}`")
            else:
                # Send error message
                await update.message.reply_text("❌ Sorry, I couldn't generate an image. Please try again with a different description.")
            
            # Add the interaction to conversation history
            user_conversations[user_id].append({"role": "user", "content": user_message})
            user_conversations[user_id].append({"role": "assistant", "content": f"I generated an image based on your request: '{prompt}'."})            
            # Manage conversation history size
            user_conversations[user_id] = manage_conversation_history(user_conversations[user_id])
            
            return
        
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
            
            # Use safe_reply to handle message sending with error handling
            await safe_reply(update, bot_reply)
        else:
            await update.message.reply_text("Sorry, I couldn't process your request. Please try again.")
    except Exception as e:
        logger.error(f"Error in handle_message: {e}\n{traceback.format_exc()}")
        await safe_reply(update, "Sorry, I encountered an error while processing your message. Please try again.")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logger.error(f"Exception while handling an update: {context.error}\n{traceback.format_exc()}")
    
    # Send message to the user
    if update and update.effective_message:
        error_message = "Sorry, I encountered an error while processing your request. Please try again later."
        try:
            await update.effective_message.reply_text(error_message)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

# Flask routes for webhook and health checks
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        # Process incoming update from Telegram
        update = Update.de_json(request.get_json(force=True), bot)
        application.process_update(update)
        return 'OK'
    except Exception as e:
        logger.error(f"Error in webhook processing: {e}\n{traceback.format_exc()}")
        return 'Error', 500

@app.route('/', methods=['GET'])
def index():
    return 'Fortec AI Bot is running!'

@app.route('/health', methods=['GET'])
def health_check():
    return {'status': 'ok'}

# Global variables for application and bot
application = None
bot = None

def main() -> None:
    """Start the bot."""
    global application, bot
    
    try:
        # Get environment variables for deployment
        PORT = int(os.environ.get('PORT', 8443))
        APP_URL = os.environ.get('APP_URL', '')
        
        # Create the bot instance
        bot = Bot(TELEGRAM_TOKEN)
        
        # Create the Application
        application = Application.builder().token(TELEGRAM_TOKEN).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CommandHandler("about", about_command))
        application.add_handler(CommandHandler("image", image_command))
        
        # Add message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Add error handler
        application.add_error_handler(error_handler)

        # Determine if we're running locally or on a server
        if APP_URL:
            # Running on server - use webhook
            logger.info(f"Starting webhook on port {PORT}")
            
            # Set webhook
            webhook_url = f"{APP_URL}/webhook"
            
            # First, delete any existing webhook
            try:
                bot.delete_webhook()
                time.sleep(0.5)  # Give Telegram some time to process
                bot.set_webhook(url=webhook_url)
                logger.info(f"Webhook set to {webhook_url}")
            except Exception as e:
                logger.error(f"Error setting webhook: {e}")
            
            # Start Flask server
            logger.info(f"Starting Flask server on port {PORT}")
            app.run(host='0.0.0.0', port=PORT, threaded=True)
        else:
            # Running locally - use polling
            logger.info("Starting polling")
            application.run_polling()
    except Exception as e:
        logger.critical(f"Critical error in main function: {e}\n{traceback.format_exc()}")
        # Try to restart if possible
        time.sleep(5)  # Wait a bit before restarting
        main()  # Attempt to restart

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Fatal error: {e}\n{traceback.format_exc()}")