"""
Gemini 2.5 Flash client for Wall Mode analysis.

Supports:
- Google AI Studio (primary, fastest)
- OpenRouter (fallback)

Usage:
    client = GeminiClient()
    response = client.analyze(wall_context, "Why does player fall through floor?")
"""

import os
import time
import httpx
from typing import Optional
from dataclasses import dataclass


@dataclass
class GeminiResponse:
    """Response from Gemini analysis."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    provider: str  # "google" or "openrouter"


class GeminiClient:
    """
    Client for Gemini 2.5 Flash API.

    Automatically selects provider based on available API keys:
    1. Google AI Studio (GOOGLE_API_KEY) - fastest
    2. OpenRouter (OPENROUTER_API_KEY) - fallback
    """

    # Model identifiers
    GOOGLE_MODEL = "gemini-2.5-flash"
    OPENROUTER_MODEL = "google/gemini-2.5-flash"

    def __init__(self):
        self.google_key = os.environ.get("GOOGLE_API_KEY")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")

        if not self.google_key and not self.openrouter_key:
            raise ValueError(
                "No API key found. Set GOOGLE_API_KEY or OPENROUTER_API_KEY in environment."
            )

        self.provider = "google" if self.google_key else "openrouter"

    def analyze(
        self,
        context: str,
        question: str,
        max_tokens: int = 8000,  # High to account for thinking tokens (model uses ~75% for reasoning)
        temperature: float = 0.3
    ) -> GeminiResponse:
        """
        Analyze codebase context and answer a question.

        Args:
            context: The Wall Mode collected context (files, code)
            question: User's question about the code
            max_tokens: Maximum response tokens
            temperature: Response creativity (lower = more focused)

        Returns:
            GeminiResponse with analysis
        """
        # Build the prompt
        system_prompt = """You are DEVA, an expert game development AI assistant analyzing a Unity codebase.

You have the FULL CODEBASE loaded via Wall Mode. Analyze the code to answer questions.

RULES:
1. Reference specific files and line numbers
2. Be direct and concise
3. If you find the issue, state it clearly
4. Suggest fixes with code snippets when relevant
5. If you need more context, say which files/systems would help

Keep responses focused - 2-4 paragraphs max unless a longer explanation is truly needed."""

        full_prompt = f"""{system_prompt}

=== CODEBASE CONTEXT ===
{context}

=== QUESTION ===
{question}

=== ANALYSIS ==="""

        if self.provider == "google":
            return self._call_google(full_prompt, max_tokens, temperature)
        else:
            return self._call_openrouter(full_prompt, max_tokens, temperature)

    def _call_google(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        max_retries: int = 3
    ) -> GeminiResponse:
        """Call Google AI Studio API directly with retry logic."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.GOOGLE_MODEL}:generateContent"

        headers = {
            "Content-Type": "application/json",
        }

        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }

        last_error = None
        for attempt in range(max_retries):
            with httpx.Client(timeout=180) as client:  # Longer timeout for large contexts
                response = client.post(
                    url,
                    headers=headers,
                    json=data,
                    params={"key": self.google_key}
                )

                if response.status_code == 200:
                    result = response.json()

                    # Extract response text
                    text = result["candidates"][0]["content"]["parts"][0]["text"]

                    # Extract token counts
                    usage = result.get("usageMetadata", {})
                    input_tokens = usage.get("promptTokenCount", 0)
                    output_tokens = usage.get("candidatesTokenCount", 0)

                    return GeminiResponse(
                        text=text,
                        model=self.GOOGLE_MODEL,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        provider="google"
                    )

                elif response.status_code == 429:
                    # Rate limit - extract retry delay and wait
                    error_data = response.json()
                    retry_delay = 60  # Default wait

                    # Try to extract suggested delay
                    details = error_data.get("error", {}).get("details", [])
                    for detail in details:
                        if detail.get("@type", "").endswith("RetryInfo"):
                            delay_str = detail.get("retryDelay", "60s")
                            retry_delay = int(float(delay_str.rstrip("s"))) + 1

                    # Check if it's a token limit issue
                    if "free_tier" in response.text:
                        raise Exception(
                            f"Free tier token limit exceeded (250K/min). "
                            f"Enable billing at https://aistudio.google.com or use smaller context. "
                            f"Retry in {retry_delay}s."
                        )

                    if attempt < max_retries - 1:
                        print(f"[Gemini] Rate limited, waiting {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        last_error = f"Rate limit exceeded after {max_retries} retries"

                else:
                    last_error = f"Google API error {response.status_code}: {response.text}"
                    break

        raise Exception(last_error)

    def _call_openrouter(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> GeminiResponse:
        """Call OpenRouter API."""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/clawdbot",  # Required by OpenRouter
        }

        data = {
            "model": self.OPENROUTER_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(url, headers=headers, json=data)

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error {response.status_code}: {response.text}")

            result = response.json()

            # Extract response text
            text = result["choices"][0]["message"]["content"]

            # Extract token counts
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return GeminiResponse(
                text=text,
                model=self.OPENROUTER_MODEL,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                provider="openrouter"
            )

    def quick_analyze(self, context: str, question: str) -> str:
        """Quick analysis returning just the text response."""
        response = self.analyze(context, question)
        return response.text


class WallAnalyzer:
    """
    High-level Wall Mode analyzer combining collection and Gemini analysis.

    Usage:
        analyzer = WallAnalyzer(project_path)
        answer = analyzer.ask("Why does player fall through floor?")
        answer = analyzer.ask("Explain the voice system", subsystem="voice")
    """

    def __init__(self, project_path: str, engine: str = "unity"):
        from voice.wall_mode import WallCollector

        self.collector = WallCollector(project_path, engine=engine)
        self.gemini = GeminiClient()
        self.last_result = None  # Cache last collection result

    def ask(
        self,
        question: str,
        subsystem: Optional[str] = None,
        query_filter: Optional[str] = None,
        force_refresh: bool = False
    ) -> str:
        """
        Ask a question about the codebase.

        Args:
            question: Question to answer
            subsystem: Filter to specific subsystem (voice, networking, etc.)
            query_filter: Keyword filter for relevant files
            force_refresh: Force re-collection even if cached

        Returns:
            Analysis response text
        """
        # Collect context (with caching)
        cache_key = (subsystem, query_filter)

        if force_refresh or self.last_result is None or self.last_result[0] != cache_key:
            print(f"[Wall] Collecting {'subsystem=' + subsystem if subsystem else 'full project'}...")
            result = self.collector.collect(subsystem=subsystem, query=query_filter)
            self.last_result = (cache_key, result)
            print(f"[Wall] Loaded {result.total_files} files, {result.total_tokens:,} tokens")
        else:
            result = self.last_result[1]
            print(f"[Wall] Using cached context ({result.total_files} files)")

        # Analyze with Gemini
        print(f"[Wall] Sending to Gemini...")
        response = self.gemini.analyze(result.context_text, question)
        print(f"[Wall] Response: {response.output_tokens} tokens from {response.provider}")

        return response.text

    def get_subsystems(self) -> dict:
        """Get available subsystems and file counts."""
        return self.collector.get_subsystem_summary()


def test_gemini():
    """Quick test of Gemini API."""
    try:
        client = GeminiClient()
        print(f"Provider: {client.provider}")

        response = client.analyze(
            context="function add(a, b) { return a + b; }",
            question="What does this code do?"
        )

        print(f"Response: {response.text[:200]}...")
        print(f"Tokens: {response.input_tokens} in, {response.output_tokens} out")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_gemini()
    else:
        # Demo with Amphitheatre
        project = r"D:\Games\PLAYA3ULL GAMES games\Amphitheatre\Amphitheatre"

        print("Wall Mode + Gemini Demo")
        print("=" * 50)

        try:
            analyzer = WallAnalyzer(project)

            print("\nSubsystems available:")
            for sub, count in analyzer.get_subsystems().items():
                print(f"  {sub}: {count} files")

            print("\n" + "=" * 50)
            question = "What files handle seating? Give me a brief overview."
            print(f"Question: {question}")
            print("=" * 50 + "\n")

            answer = analyzer.ask(question, subsystem="seating")
            print(answer)

        except ValueError as e:
            print(f"\nSetup needed: {e}")
            print("\nTo use Wall Mode with Gemini:")
            print("  1. Get API key from https://aistudio.google.com/apikey")
            print("  2. Set environment variable: GOOGLE_API_KEY=your_key_here")
