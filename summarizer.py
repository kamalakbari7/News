import logging

from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from config import OPENAI_API_KEY, OPENAI_MODEL, MAX_SUMMARY_TOKENS

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "You are a news summarizer. Provide a concise 2-3 sentence summary of the "
    "following news article. Focus on the key facts and significance."
)


def summarize_article(article: dict) -> str:
    """Summarize a single article using OpenAI GPT.

    Falls back to the article's description if the API call fails.
    """
    content = article.get("content", "") or article.get("description", "")
    if not content:
        return article.get("description", "No summary available.")

    # Truncate to ~3000 chars to control token usage
    content = content[:3000]
    user_message = f"Title: {article['title']}\n\nContent: {content}"

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=MAX_SUMMARY_TOKENS,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except RateLimitError as e:
        logger.warning("OpenAI rate limit hit: %s. Using fallback.", e)
        return article.get("description", "No summary available.")
    except APIConnectionError as e:
        logger.warning("OpenAI connection error: %s. Using fallback.", e)
        return article.get("description", "No summary available.")
    except APIError as e:
        logger.warning("OpenAI API error: %s. Using fallback.", e)
        return article.get("description", "No summary available.")
