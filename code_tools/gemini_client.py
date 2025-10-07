"""
Gemini API Client with Rate Limiting
Handles code editing and error correction using Gemini 2.5 Flash
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import os
from dotenv import load_dotenv
from google import genai
import re
load_dotenv()


logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """Rate limiting configuration"""

    requests_per_minute: int = 15  # 15 RPM
    tokens_per_minute: int = 250_000  # 250K TPM
    requests_per_day: int = 1_000  # 1K RPD

    # Internal tracking
    minute_requests: List[float] = None
    day_requests: List[float] = None
    minute_tokens: List[tuple[float, int]] = None  # (timestamp, token_count)

    def __post_init__(self):
        if self.minute_requests is None:
            self.minute_requests = []
        if self.day_requests is None:
            self.day_requests = []
        if self.minute_tokens is None:
            self.minute_tokens = []


class GeminiClient:
    """Gemini API client with rate limiting and code editing capabilities"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini client

        Args:
            api_key: Gemini API key (if None, will use environment variable)
        """
        self.client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self.rate_limit = RateLimit()
        self.model = "gemini-2.5-flash"

        # Statistics
        self.total_requests = 0
        self.total_tokens = 0
        self.failed_requests = 0

    async def _check_rate_limits(self, estimated_tokens: int = 1000) -> bool:
        """
        Check if we can make a request within rate limits

        Args:
            estimated_tokens: Estimated token count for the request

        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()

        # Clean old entries
        self._clean_old_entries(now)

        # Check requests per minute
        if len(self.rate_limit.minute_requests) >= self.rate_limit.requests_per_minute:
            logger.warning("Rate limit exceeded: requests per minute")
            return False

        # Check requests per day
        if len(self.rate_limit.day_requests) >= self.rate_limit.requests_per_day:
            logger.warning("Rate limit exceeded: requests per day")
            return False

        # Check tokens per minute
        current_minute_tokens = sum(
            tokens
            for timestamp, tokens in self.rate_limit.minute_tokens
            if now - timestamp < 60
        )

        if current_minute_tokens + estimated_tokens > self.rate_limit.tokens_per_minute:
            logger.warning("Rate limit exceeded: tokens per minute")
            return False

        return True

    def _clean_old_entries(self, now: float):
        """Remove old entries from rate limit tracking"""
        # Remove entries older than 1 minute
        self.rate_limit.minute_requests = [
            req_time
            for req_time in self.rate_limit.minute_requests
            if now - req_time < 60
        ]

        self.rate_limit.minute_tokens = [
            (timestamp, tokens)
            for timestamp, tokens in self.rate_limit.minute_tokens
            if now - timestamp < 60
        ]

        # Remove entries older than 1 day
        self.rate_limit.day_requests = [
            req_time
            for req_time in self.rate_limit.day_requests
            if now - req_time < 86400  # 24 hours
        ]

    def _record_request(self, token_count: int):
        """Record a successful request"""
        now = time.time()
        self.rate_limit.minute_requests.append(now)
        self.rate_limit.day_requests.append(now)
        self.rate_limit.minute_tokens.append((now, token_count))

        self.total_requests += 1
        self.total_tokens += token_count

    async def _wait_for_rate_limit(self, estimated_tokens: int = 1000) -> None:
        """Wait until we can make a request within rate limits"""
        max_attempts = 60  # Maximum 60 seconds wait
        attempt = 0

        while (
            not await self._check_rate_limits(estimated_tokens)
            and attempt < max_attempts
        ):
            await asyncio.sleep(1)
            attempt += 1

        if attempt >= max_attempts:
            raise Exception("Rate limit wait timeout exceeded")

    async def generate_content(self, prompt: str) -> str:
        """
        Generate content using Gemini with rate limiting

        Args:
            prompt: The prompt to send to Gemini
            **kwargs: Additional parameters for the API call

        Returns:
            Generated content as string

        Raises:
            Exception: If API call fails or rate limits exceeded
        """
        # Estimate token count (rough approximation)
        estimated_tokens = len(prompt.split()) * 1.3  # Rough token estimation

        # Wait for rate limit if needed
        await self._wait_for_rate_limit(int(estimated_tokens))

        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt
            )

            # Record successful request
            actual_tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
            self._record_request(actual_tokens) #type:ignore

            return response.text if response.text else ""


        except Exception as e:
            self.failed_requests += 1
            logger.error(f"Gemini API call failed: {e}")
            raise

    async def edit_code(
        self,
        file_content: str,
        edit_instructions: str,
        code_edit: str,
        file_path: str,
        language: Optional[str] = None,
    ) -> str:
        """
        Edit code using Gemini

        Args:
            file_content: Current content of the file
            edit_instructions: Human instructions for the edit
            code_edit: The edit content with // ... existing code ... markers
            file_path: Path to the file being edited
            language: Programming language (auto-detected if None)

        Returns:
            Complete rewritten file content
        """

        # Detect language from file extension if not provided
        if not language:
            if file_path.endswith(".py"):
                language = "python"
            elif file_path.endswith((".js", ".jsx")):
                language = "javascript"
            elif file_path.endswith((".ts", ".tsx")):
                language = "typescript"
            elif file_path.endswith(".html"):
                language = "html"
            elif file_path.endswith(".css"):
                language = "css"
            else:
                language = "text"

        prompt = f"""You are a code editing assistant. Your task is to apply the requested edit to the existing file while preserving all unchanged code exactly as it is.

**File Path**: {file_path}
**Language**: {language}

**Current File Content**:
```{language}
{file_content}
```

**Edit Instructions**: {edit_instructions}

**Edit Content** (with // ... existing code ... markers):
```{language}
{code_edit}
```

**Your Task**:
1. Apply the edit to the existing file content
2. The `// ... existing code ...` comments represent unchanged parts - preserve them exactly
3. Only modify the parts that are explicitly shown in the edit content
4. Maintain proper indentation and code structure
5. Preserve all imports, comments, and existing functionality
6. Return the complete rewritten file content

**Important**:
- Return ONLY the complete file content, no explanations
- Do not add any markdown formatting or code blocks
- Preserve exact spacing, indentation, and formatting
- Do not remove or modify any existing code that isn't part of the edit"""

        try:
            raw_result = await self.generate_content(prompt)
            # Find and extract content from a markdown code block
            match = re.search(r"```(?:\w+)?\n(.*?)\n```", raw_result, re.DOTALL)
            if match:
                result = match.group(1)
            else:
                result = raw_result
            return result.strip()
        
        except Exception as e:
            logger.error(f"Code edit failed: {e}")
            raise Exception(f"Failed to edit code: {str(e)}")

    async def fix_code_errors(
        self,
        file_content: str,
        errors: List[str],
        file_path: str,
        language: Optional[str] = None,
        original_edit_context: Optional[str] = None,
    ) -> str:
        """
        Fix code errors using Gemini

        Args:
            file_content: Current file content with errors
            errors: List of error messages
            file_path: Path to the file
            language: Programming language
            original_edit_context: Context about what was being edited

        Returns:
            Fixed file content
        """

        if not language:
            if file_path.endswith(".py"):
                language = "python"
            elif file_path.endswith((".js", ".jsx")):
                language = "javascript"
            elif file_path.endswith((".ts", ".tsx")):
                language = "typescript"
            else:
                language = "text"

        error_list = "\n".join(f"- {error}" for error in errors)

        context_info = (
            f"\n**Original Edit Context**: {original_edit_context}"
            if original_edit_context
            else ""
        )

        prompt = f"""You are a code error fixing assistant. The following code has errors that need to be fixed.

**File Path**: {file_path}
**Language**: {language}{context_info}

**Current Code with Errors**:
```{language}
{file_content}
```

**Errors to Fix**:
{error_list}

**Your Task**:
1. Fix all the listed errors
2. Maintain the overall code structure and functionality
3. Preserve all working parts of the code
4. Ensure proper syntax and formatting
5. Do not change functionality unless required to fix errors

**Important**:
- Return ONLY the complete corrected file content
- No explanations or markdown formatting
- Fix errors while preserving intended functionality"""

        try:
            result = await self.generate_content(prompt)
            return result.strip()

        except Exception as e:
            logger.error(f"Code error fixing failed: {e}")
            raise Exception(f"Failed to fix code errors: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "failed_requests": self.failed_requests,
            "success_rate": (self.total_requests - self.failed_requests)
            / max(self.total_requests, 1),
            "current_rate_limits": {
                "minute_requests": len(self.rate_limit.minute_requests),
                "day_requests": len(self.rate_limit.day_requests),
                "minute_tokens": sum(
                    tokens for _, tokens in self.rate_limit.minute_tokens
                ),
            },
        }
