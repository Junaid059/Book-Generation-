import logging
import asyncio
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import APIError, APITimeoutError, RateLimitError, BadRequestError

from app.config import get_settings

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


RETRY_EXCEPTIONS = (APITimeoutError, RateLimitError)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
    before_sleep=lambda retry_state: logger.warning(
        f"LLM call failed, retrying (attempt {retry_state.attempt_number})..."
    ),
)
async def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Low-level LLM call with retry logic."""
    settings = get_settings()
    response = await _get_client().chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


async def generate_outline(title: str, notes: str) -> str:
    """Generate a book outline from title and notes."""
    system_prompt = (
        "You are a professional book author and editor. Generate a detailed book outline "
        "with chapter titles and brief descriptions for each chapter. The outline should be "
        "well-structured and comprehensive."
    )
    user_prompt = (
        f"Generate a detailed book outline for a book titled: \"{title}\"\n\n"
        f"Author's notes and guidance:\n{notes}\n\n"
        "Please provide:\n"
        "1. A list of chapters with titles\n"
        "2. A brief description (2-3 sentences) of what each chapter covers\n"
        "3. The chapters should flow logically and build upon each other\n\n"
        "Format each chapter as:\n"
        "Chapter N: [Title]\n"
        "[Description]\n"
    )
    logger.info(f"Generating outline for book: {title}")
    return await _call_llm(system_prompt, user_prompt, max_tokens=4000)


async def generate_chapter(
    title: str,
    outline: str,
    chapter_number: int,
    chapter_title: str,
    previous_summaries: str,
    chapter_notes: str | None = None,
) -> str:
    """Generate a single chapter with context from previous chapters."""
    system_prompt = (
        "You are a professional book author. Write a complete, detailed book chapter. "
        "Maintain consistency with previously written chapters. Write in a professional, "
        "engaging style appropriate for the book's subject matter."
    )

    context_block = ""
    if previous_summaries:
        context_block = (
            f"\n\nSummaries of previous chapters for continuity:\n{previous_summaries}\n"
        )

    notes_block = ""
    if chapter_notes:
        notes_block = f"\n\nAdditional notes for this chapter:\n{chapter_notes}\n"

    user_prompt = (
        f"Book Title: \"{title}\"\n\n"
        f"Full Book Outline:\n{outline}\n"
        f"{context_block}"
        f"{notes_block}"
        f"\nWrite Chapter {chapter_number}: {chapter_title}\n\n"
        "Write a complete, detailed chapter (at least 1500 words). "
        "Maintain consistency and continuity with previously written chapters."
    )
    logger.info(f"Generating chapter {chapter_number}: {chapter_title}")
    return await _call_llm(system_prompt, user_prompt, max_tokens=4000)


async def summarize_chapter(content: str) -> str:
    """Generate a concise summary of a chapter for context continuity."""
    system_prompt = (
        "You are a professional editor. Summarize the following book chapter concisely, "
        "capturing key events, themes, arguments, and character developments. "
        "This summary will be used to maintain continuity when writing subsequent chapters."
    )
    user_prompt = (
        f"Summarize this chapter in 3-5 paragraphs:\n\n{content}"
    )
    logger.info("Generating chapter summary")
    return await _call_llm(system_prompt, user_prompt, max_tokens=1500)
