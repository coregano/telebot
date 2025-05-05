#!/usr/bin/env python
import logging
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, InlineQueryHandler
from dotenv import load_dotenv
from pathlib import Path
import os
from uuid import uuid4

# Import yt2spotify components
from yt2spotify.converter import Converter
from yt2spotify.services.spotify import SpotifyService
from yt2spotify.services.youtube_music import YoutubeMusicService

# Load environment variables
dotenv_path = Path(__file__).parent / "api.env"
load_dotenv(dotenv_path)

# Validate required environment variables
required_vars = ['TELE_API_KEY', 'SPOTIPY_CLIENT_ID', 'SPOTIPY_CLIENT_SECRET', 'YOUTUBE_API_KEY']
for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")

# Access environment variables
tele_api_key = os.getenv("TELE_API_KEY")
spotify_client_id = os.getenv("SPOTIPY_CLIENT_ID")
spotify_client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Suppress unnecessary logs from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def convert_link(link: str):
    """
    Converts a link between Spotify and YouTube Music.
    Returns the first search result (music item) or an error message.
    """
    # Detect the source service
    for cls in [SpotifyService, YoutubeMusicService]:
        if cls.detect(link):
            from_service = cls.name
            break
    else:
        return "Unsupported link. Please provide a valid Spotify or YouTube Music link."

    try:
        # Determine the target service
        to_service = "youtube_music" if from_service == "spotify" else "spotify"

        # Perform the conversion
        converter = Converter.by_names(from_service_name=from_service, to_service_name=to_service)
        result = converter.convert(link)

        # Check if there are results
        if hasattr(result, 'results') and len(result.results) > 0:
            return result.results[0]  # Return the first result
        else:
            return "No results found for the given link."

    except Exception as e:
        logger.error(f"Error during link conversion: {e}")
        return "An error occurred while converting the link. Please try again later."

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text("Welcome! Send me a Spotify or YouTube Music link, and I'll convert it for you.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular chat messages."""
    user_message = update.message.text
    converted_link = convert_link(user_message)

    if isinstance(converted_link, str):  # Error message
        await update.message.reply_text(converted_link)
    else:
        await update.message.reply_text(converted_link.url)

# Inline Query Handler
async def inline_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries."""
    query = update.inline_query.query
    if not query:  # Empty query should not be handled
        return

    results = []
    try:
        converted_music = convert_link(query)

        if isinstance(converted_music, str):  # Error message
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title="Error",
                    input_message_content=InputTextMessageContent(converted_music),
                )
            )
        else:
            # Add multiple results if available (e.g., top 3 matches)
            for item in getattr(converted_music, 'results', [])[:3]:  # Limit to top 3 results
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title=item.description1,
                        description=f"{item.description2} - {item.description3}",
                        thumbnail_url=item.art_url,
                        input_message_content=InputTextMessageContent(item.url),
                    )
                )

    except Exception as e:
        logger.error(f"Error during inline query: {e}")
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title="Error",
                input_message_content=InputTextMessageContent("An error occurred while processing your request."),
            )
        )

    await context.bot.answer_inline_query(update.inline_query.id, results)

# Global Error Handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# Main Function
if __name__ == '__main__':
    # Build the application
    application = ApplicationBuilder().token(tele_api_key).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(InlineQueryHandler(inline_convert))

    # Add global error handler
    application.add_error_handler(error_handler)

    # Start polling
    application.run_polling()