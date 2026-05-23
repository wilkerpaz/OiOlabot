import json
import logging
from typing import Tuple

import httpx

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Classify Telegram Bot API errors to determine retry vs deactivation strategy."""

    # Patterns that indicate permanent errors (bot cannot send to this user/chat)
    PERMANENT_ERROR_PATTERNS = [
        "blocked by the user",
        "not a member of the supergroup",
        "not a member of the channel",
        "not a member of the group",
        "chat not found",
        "user is deactivated",
        "user_is_deleted",
        "chat_deleted",
    ]

    @staticmethod
    def classify_response(response: httpx.Response) -> Tuple[str, dict | None]:
        """
        Classify a Telegram Bot API response.

        Returns:
            Tuple of (strategy, error_details)
            strategy: "success", "permanent", "transient", or "unknown"
            error_details: dict with "code", "description" if error
        """
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("ok"):
                    return "success", None
            except:
                pass

        # Parse error response
        try:
            data = response.json()
            error_code = data.get("error_code", response.status_code)
            description = data.get("description", response.text)
        except:
            error_code = response.status_code
            description = response.text

        error_details = {
            "code": error_code,
            "description": description,
        }

        # Classify based on HTTP status and description
        if error_code in [403, 400]:
            # Check if it's a permanent error
            if ErrorHandler._is_permanent_error(description):
                return "permanent", error_details
            # Otherwise treat as transient (e.g., temporary permission issue)
            return "transient", error_details

        if error_code in [429]:
            # Rate limit - transient
            return "transient", error_details

        if error_code >= 500:
            # Server error - transient
            return "transient", error_details

        # Unknown or unexpected error
        return "unknown", error_details

    @staticmethod
    def _is_permanent_error(description: str) -> bool:
        """Check if error description indicates a permanent (unrecoverable) error."""
        description_lower = description.lower()
        return any(
            pattern in description_lower
            for pattern in ErrorHandler.PERMANENT_ERROR_PATTERNS
        )

    @staticmethod
    def log_error(chat_id: int, error_details: dict | None, strategy: str) -> None:
        """Log error with appropriate level based on strategy."""
        if error_details is None:
            return

        code = error_details.get("code", "?")
        desc = error_details.get("description", "Unknown error")

        if strategy == "permanent":
            logger.error(
                f"Permanent error for chat {chat_id} (code {code}): {desc} — disabling subscription"
            )
        elif strategy == "transient":
            logger.warning(
                f"Transient error for chat {chat_id} (code {code}): {desc} — will retry next cycle"
            )
        else:
            logger.warning(
                f"Unknown error for chat {chat_id} (code {code}): {desc}"
            )
