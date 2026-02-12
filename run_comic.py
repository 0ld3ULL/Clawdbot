"""
Generate a comic parable.

Usage:
    python run_comic.py                          # Uses default parable
    python run_comic.py "The Baker's Oven"       # Custom theme
    python run_comic.py --script-only "theme"    # Preview script only (no images, free)
"""

import asyncio
import sys
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from comic_pipeline import ComicParablePipeline


# Default parable if none provided
DEFAULT_THEME = (
    "The Fisherman's Free Net — A fisherman in a coastal village is given "
    "a free net by a stranger from the kingdom. Best net he's ever used. "
    "Then he notices it counts every fish and reports his catch to someone "
    "he's never met."
)


async def main():
    script_only = "--script-only" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--script-only"]
    theme = " ".join(args) if args else DEFAULT_THEME

    pipeline = ComicParablePipeline()

    if script_only:
        print(f"\nGenerating script only (free)...")
        print(f"Theme: {theme[:80]}...\n")
        project = await pipeline.generate_script_only(theme=theme)
        print(f"Title: {project.title}")
        print(f"Synopsis: {project.synopsis}")
        print(f"Panels: {len(project.panels)}\n")

        # Show the full parable prose
        if hasattr(project, 'parable_text') and project.parable_text:
            word_count = len(project.parable_text.split())
            print(f"{'=' * 50}")
            print(f"THE PARABLE ({word_count} words)")
            print(f"{'=' * 50}")
            print(f"{project.parable_text}")
            print(f"{'=' * 50}\n")

        # Show comic panels
        print(f"COMIC PANELS:")
        for p in project.panels:
            print(f"\n--- Panel {p.panel_number} [{p.camera.value}] ---")
            if p.narration:
                print(f"  Narration: \"{p.narration}\"")
            for d in p.dialogue:
                print(f"  {d['speaker']}: \"{d['text']}\"")
            print(f"  [Image: {p.image_prompt[:80]}...]")
        print(f"\nCost: ${project.total_cost:.4f}")
    else:
        print(f"\nGenerating full comic (~$0.41)...")
        print(f"Theme: {theme[:80]}...\n")
        project = await pipeline.generate(theme=theme)
        print(f"\n{'=' * 50}")
        print(f"DONE!")
        print(f"  Title: {project.title}")
        print(f"  Panels: {len(project.panels)}")
        print(f"  PDF: {project.pdf_path}")
        print(f"  Video: {project.video_path}")
        print(f"  Social panels: {len(project.panel_exports)}")
        print(f"  Output folder: {project.output_dir}")
        print(f"  Total cost: ${project.total_cost:.4f}")

    await pipeline.close()


if __name__ == "__main__":
    asyncio.run(main())
