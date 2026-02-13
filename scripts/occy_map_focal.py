"""
Map the current Focal ML interface.

Sends Occy's browser through Focal ML with broad mapping tasks to discover
what's actually there NOW (not what the March 2025 tutorials said).

Usage:
    venv/Scripts/python.exe scripts/occy_map_focal.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Browser-use event bus timeouts
os.environ.setdefault("TIMEOUT_BrowserStartEvent", "120")
os.environ.setdefault("TIMEOUT_BrowserLaunchEvent", "120")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("focal_mapper")

# Mapping tasks — broad, exploratory, no assumptions about feature names
MAPPING_TASKS = [
    {
        "name": "main_navigation",
        "prompt": (
            "You are on focalml.com. Catalog the ENTIRE main navigation structure. "
            "List every menu item, sidebar link, top bar button, and navigation element you can see. "
            "For each one, note: its exact label, where it is (top bar, sidebar, etc.), "
            "and what it seems to do. Be thorough — click on each main section briefly to see "
            "what's inside, then come back. DO NOT start any projects or spend credits."
        ),
        "max_steps": 20,
    },
    {
        "name": "project_creation_flow",
        "prompt": (
            "Navigate to create a new project in Focal ML. Go through the ENTIRE project "
            "creation workflow step by step, but DO NOT submit or spend credits. "
            "At each step, catalog: every dropdown, input field, button, toggle, and option you see. "
            "For dropdowns, click them open and list ALL available choices. "
            "Note the exact labels of everything. List what video models are available if you see a "
            "model selector. List what input methods are available (idea, script, JSON, etc). "
            "Go as deep as you can without spending credits."
        ),
        "max_steps": 25,
    },
    {
        "name": "templates_and_library",
        "prompt": (
            "Navigate to the Templates section (or any library/browse area) in Focal ML. "
            "Catalog what categories of templates exist, what kinds of content they cover, "
            "and how many there are. Also check if there's a Characters section, a Locations "
            "section, or any asset library. List everything you find with exact labels."
        ),
        "max_steps": 15,
    },
    {
        "name": "account_and_settings",
        "prompt": (
            "Click on your profile/account area in Focal ML. Catalog everything in the "
            "account menu: subscription info, credit balance, settings options, etc. "
            "If there's a settings page, go into it and list all available settings. "
            "Note the exact subscription plan name and credit count."
        ),
        "max_steps": 15,
    },
    {
        "name": "editor_and_tools",
        "prompt": (
            "Find and open an existing project in Focal ML (or create a draft without submitting). "
            "Once in the editor/workspace, catalog EVERY tool, panel, button, and option available. "
            "Look for: timeline, chat/co-pilot, scene list, voice/TTS options, music options, "
            "export/render buttons, character tools, anything. List the exact label and location "
            "of everything. DO NOT render or spend credits."
        ),
        "max_steps": 25,
    },
]

OUTPUT_PATH = Path("data/focal_interface_map.json")


async def main():
    from agents.occy_browser import FocalBrowser

    browser = FocalBrowser(headless=False)

    logger.info("Starting browser...")
    success = await browser.start()
    if not success:
        logger.error("Failed to start browser")
        return

    # Check login
    logged_in = await browser.check_login()
    if not logged_in:
        logger.warning("Not logged in — please log in manually in the browser window")
        logger.info("Waiting 30 seconds for manual login...")
        await asyncio.sleep(30)
        logged_in = await browser.check_login()
        if not logged_in:
            logger.error("Still not logged in — aborting")
            await browser.stop()
            return

    logger.info("Logged in — starting interface mapping")

    results = {}
    for task in MAPPING_TASKS:
        name = task["name"]
        logger.info(f"\n{'='*60}")
        logger.info(f"MAPPING: {name}")
        logger.info(f"{'='*60}")

        result = await browser.run_task(task["prompt"], max_steps=task["max_steps"])

        results[name] = {
            "success": result["success"],
            "steps": result["steps_taken"],
            "result": result.get("result", ""),
            "error": result.get("error"),
            "disconnected": result.get("disconnected", False),
        }

        logger.info(f"  Success: {result['success']}, Steps: {result['steps_taken']}")

        # Take screenshot after each mapping
        await browser.take_screenshot(f"map_{name}")

        if result.get("disconnected"):
            logger.warning("Browser disconnected — attempting restart")
            restarted = await browser.restart()
            if not restarted:
                logger.error("Browser restart failed — saving partial results")
                break

        # Brief pause
        await asyncio.sleep(2)

    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "mapped_at": datetime.now().isoformat(),
        "tasks": results,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"\nResults saved to {OUTPUT_PATH}")

    # Print summary
    print("\n" + "=" * 60)
    print("FOCAL ML INTERFACE MAP")
    print("=" * 60)
    for name, data in results.items():
        print(f"\n--- {name} ---")
        if data["result"]:
            print(data["result"][:2000])
        elif data["error"]:
            print(f"ERROR: {data['error']}")

    await browser.stop()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
