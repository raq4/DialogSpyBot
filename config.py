# environment variables
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
MY_USER_ID: int = int(os.getenv("MY_USER_ID", "0"))
DB_PATH: str = os.getenv("DB_PATH", "messages_cache.db")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")