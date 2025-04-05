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
logger = logging.getLogger(__name__)

def convert_link(link: str): # returns the music item containing url, description etc
    # Detect the source service
    for cls in [SpotifyService, YoutubeMusicService]:
        if cls.detect(link):
            from_service = cls.name
            break
    else:
        return "Unsupported link. Please provide a valid Spotify or Youtube Music link."

    # Convert the link
    try:
        if (from_service == "spotify"): # duality, change if adding more services 
            to_service = "youtube_music"
        else:
            to_service = "spotify"

        converter = Converter.by_names(from_service_name=from_service, to_service_name=to_service)
        result = converter.convert(link)

        # Access the URL from the first search result
        if hasattr(result, 'results') and len(result.results) > 0:
            first_result = result.results[0] # get the first result
            return first_result  # Return the music item 
        else:
            return "No results found for the given link."

    except Exception as e:
        logger.error(f"Error during link conversion: {e}")
        return "An error occurred while converting the link. Please try again later."

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send me a Spotify or YouTube Music link, and I'll convert it for you.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): # change to show more results mayb
    user_message = update.message.text
    converted_link = convert_link(user_message)
    await update.message.reply_text(converted_link.url)

# inline function 
async def inline_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query:
        return

    results = []
    try:
        converted_music = convert_link(query)
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                thumbnail_url=converted_music.art_url,  # Add the album art as a thumbnail
                title=converted_music.description1,  # Use the track title as the title
                description=f"{converted_music.description2} - {converted_music.description3}",  # Use artist and album as the description
                input_message_content=InputTextMessageContent(converted_music.url)  # Use the URL as the message content 
            )
        )

    except Exception as e:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title='Error',
                input_message_content=InputTextMessageContent("An error occurred while converting the link.")
            )
        )

    await context.bot.answer_inline_query(update.inline_query.id, results)

# Main function
if __name__ == '__main__':
    application = ApplicationBuilder().token(tele_api_key).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(InlineQueryHandler(inline_convert))

    # Start polling
    application.run_polling()
