# Fortec AI Telegram Bot

A Telegram chatbot powered by DeepSeek AI, created by ERES.

## Features

- Integrates with DeepSeek AI for intelligent responses
- Maintains conversation history for each user
- Provides helpful commands: /start, /help, and /reset

## Setup Instructions

### Local Development

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the bot:
   ```
   python fortecai_bot.py
   ```

### Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python fortecai_bot.py`
4. Add the following environment variables:
   - No additional environment variables needed as tokens are hardcoded (not recommended for production)

## Commands

- `/start` - Start the conversation
- `/help` - Show help message
- `/reset` - Reset conversation history

## Security Note

For production deployment, it's recommended to move the Telegram token to environment variables instead of hardcoding it in the script.

## Created By

ERES