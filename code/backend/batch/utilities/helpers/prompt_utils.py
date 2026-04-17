"""Utility functions for prompt construction."""

from datetime import datetime


def get_current_date_suffix() -> str:
    """Returns a string with today's date to append to system prompts,
    so the LLM is aware of the current date."""
    today = datetime.now().strftime("%B %d, %Y")
    return (
        f"\nDate Handling Rules:"
        f"\n-For queries like 'next', 'upcoming', 'future', or 'after today', only consider dates later than the current date."
        f"\n-Ignore past dates unless explicitly requested."
        f"\n-If no future dates exist in the retrieved documents, respond:"
        f'\n  "No future records found. All available dates are in the past."'
        f"\n-Never return a past date as the next or upcoming item."
        f"\nToday's date is {today}."
    )
