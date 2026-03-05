import os

# Set required env vars before any config import
os.environ.setdefault("NEWSAPI_KEY", "test-newsapi-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("GMAIL_ADDRESS", "test@gmail.com")
os.environ.setdefault("GMAIL_APP_PASSWORD", "test-app-password")
os.environ.setdefault("EMAIL_RECIPIENT", "test@gmail.com")
