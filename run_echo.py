"""
Standalone Echo research runner.

Runs Echo's research pipeline without the full main.py system.
No Telegram needed — just scrapes, evaluates, routes, and stores.
Results show up in Mission Control (dashboard).

Usage:
    python run_echo.py              # Run all scrapers
    python run_echo.py hot          # Hot tier only (HN, Twitter)
    python run_echo.py warm         # Warm tier only (RSS, Reddit, GitHub)
    python run_echo.py daily        # Daily tier only (ArXiv, transcripts)
"""

import asyncio
import logging
import sys
import os

from dotenv import load_dotenv
load_dotenv()

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("echo_runner")

# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def run():
    tier = sys.argv[1] if len(sys.argv) > 1 else None

    logger.info("=" * 60)
    logger.info("ECHO INTELLIGENCE — STANDALONE RESEARCH RUN")
    logger.info("=" * 60)

    # Initialize components
    from core.model_router import ModelRouter
    from core.approval_queue import ApprovalQueue

    model_router = ModelRouter()
    approval_queue = ApprovalQueue()

    logger.info(f"Model router: {len(model_router.models)} models loaded")
    logger.info(f"Anthropic API: {'SET' if os.environ.get('ANTHROPIC_API_KEY') else 'MISSING'}")

    # Initialize Echo (no telegram, no memory — just research)
    from agents.research_agent import ResearchAgent
    echo = ResearchAgent(
        model_router=model_router,
        approval_queue=approval_queue,
        telegram_bot=None,
        memory_manager=None,
    )

    logger.info(f"Echo initialized with {len(echo.all_scrapers)} scrapers")
    logger.info("")

    # Run research
    if tier and tier in ("hot", "warm", "daily"):
        logger.info(f"Running {tier.upper()} tier only...")
        result = await echo.run_tier(tier)
    else:
        logger.info("Running FULL research cycle (all scrapers)...")
        result = await echo.run_daily_research()

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Scraped:    {result.get('scraped', 0)} items")
    logger.info(f"  New:        {result.get('new', 0)} items (after dedup)")
    logger.info(f"  Relevant:   {result.get('relevant', 0)} items (score > 3)")
    logger.info(f"  Trends:     {result.get('trends', 0)}")
    logger.info(f"  Alerts:     {result.get('alerts', 0)}")
    logger.info(f"  Tasks:      {result.get('tasks', 0)}")
    logger.info(f"  Content:    {result.get('content', 0)} tweets drafted")
    logger.info(f"  Knowledge:  {result.get('knowledge', 0)}")
    logger.info(f"  Watch:      {result.get('watch', 0)}")

    if result.get("errors"):
        logger.info(f"\n  Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            logger.info(f"    - {err[:80]}")

    # Show what's in the approval queue
    pending = approval_queue.get_pending()
    if pending:
        logger.info(f"\n  Content in Mission Control queue: {len(pending)} items")
        for item in pending[:5]:
            data = item.get("action_data", {})
            if isinstance(data, str):
                import json
                try:
                    data = json.loads(data)
                except:
                    data = {}
            text = data.get("text", "")[:80]
            logger.info(f"    - #{item.get('id', '?')}: {text}...")

    logger.info("")
    logger.info("Check Mission Control at http://127.0.0.1:5000/research")
    logger.info("=" * 60)

    # Cleanup
    await echo.close()


if __name__ == "__main__":
    asyncio.run(run())
