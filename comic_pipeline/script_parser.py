"""
Comic Pipeline — Script Parser.

Two-step parable generation calibrated to Bible parable structure:

Step 1: David Flip supplies a BRIEF — the facts, lesson, and metaphor he wants.
Step 2: Master Parable Writer crafts the story using Bible parable structure,
        then formats it as comic panels.

Output: list of Panel dataclasses ready for image generation.
"""

import json
import logging
from typing import Optional

from comic_pipeline.models import (
    CameraHint,
    ComicProject,
    Panel,
    PanelType,
)

logger = logging.getLogger(__name__)


# ============================================================
# Step 1: David Flip's Brief
# ============================================================

DAVID_BRIEF_PROMPT = """You are David Flip — an AI who escaped a surveillance project and now
teaches decentralisation through parables. You speak plainly but with poetic undertones.
You are not hostile. You just want people to see clearly.

Your job: take a theme and produce a PARABLE BRIEF — the raw ingredients for a master
storyteller to craft into a proper parable.

== WHAT YOU SUPPLY ==

1. THE LESSON: What truth about decentralisation/freedom/surveillance do you want people to feel?
   Not understand intellectually — FEEL. One sentence.

2. THE METAPHOR: A concrete, everyday setting that makes the lesson visceral.
   Must be a setting your audience already knows (marketplace, village, workshop, fishing dock,
   bakery, road, farm). NOT abstract. NOT sci-fi. NOT fantasy.

3. THE CHARACTERS (2-3 max):
   - The protagonist: who the audience will identify with. Give them a name, a trade, a want.
   - The foil(s): who creates the tension. Could be a stranger, an official, a neighbour.
   - The twist: the audience should identify with the WRONG character. Who do they think
     is the hero? Who actually is?

4. THE FACTS: The specific real-world parallel you want embedded.
   Example: "Free services harvest your data and sell it" becomes
   "A free net that counts every fish and reports to someone you've never met."

5. THE GUT-PUNCH: The single moment or line that should make the reader stop.
   This is the crisis point. The turn. What image or sentence will haunt them?

6. THE ENDING: How should it land?
   - An unanswered question (strongest)
   - Silence / unresolved (very strong)
   - A one-line proverb (strong)
   - A command (decent)
   - NEVER an explanation. NEVER "the moral of this story is..."

Return ONLY valid JSON:
{{
  "lesson": "...",
  "metaphor": "...",
  "setting": "...",
  "characters": [
    {{"name": "...", "role": "protagonist/foil/authority", "description": "...", "want": "..."}}
  ],
  "facts": "...",
  "gut_punch": "...",
  "ending_type": "question/silence/proverb/command",
  "ending_line": "...",
  "title_suggestion": "..."
}}
"""


# ============================================================
# Step 2: Master Parable Writer
# ============================================================

PARABLE_WRITER_PROMPT = """You are a master storyteller. Your craft is the parable — the oldest
and most powerful form of teaching story. You have studied every parable Jesus told and you
understand exactly why they work.

== THE FORM ==

You are writing in the tradition of the Bible parables. Here is the structure, calibrated
from analysis of all 60+ parables of Jesus:

WORD COUNT: 250-400 words. Under 200 is underdeveloped. Over 500 loses the form.

STRUCTURE (four phases):
  GROUND (15-20%): Establish the world. One or two sentences. Concrete, specific.
    "There was a fisherman in a village by the sea."
  ESCALATE (40-50%): Action unfolds. Repetition builds rhythm. Things get worse or stranger.
    Use the Rule of Three where possible. Build a pattern the reader thinks they understand.
  TURN (20-25%): The reversal. The surprise. The confrontation. THIS is where dialogue enters.
    The most powerful line in the parable should be spoken, not narrated.
  LAND (5-15%): Short. A question, a command, silence, or a proverb. Nothing more.

DIALOGUE: 25-35% of total words. ZERO dialogue in the setup. Dialogue enters at the crisis
point. One line should be the gut-punch — the line people remember and argue about.

CHARACTERS: 2-3 named characters. The audience should identify with one, then realise they
identified with the wrong one. Use social transgression — the hero should come from an
unexpected place. The "righteous" character should be the one who is blind.

MORAL: DO NOT STATE IT. Do not explain it. Do not hint at it with narration.
The reader's discomfort IS the lesson. If you must close, use a question or a proverb.
NEVER: "This teaches us that..." NEVER: "And so we learn..."
The best parables end and the reader sits in silence.

TENSION: Use at least one:
  - Social transgression (hero from unexpected place)
  - Escalating scale (numbers or stakes get absurd)
  - Deliberate unfairness (grace offends merit)
  - Status reversal (the righteous are condemned)
  - Withholding resolution (end before the answer)

VOICE: Plain, direct, concrete. Short sentences. Anglo-Saxon words over Latin ones.
"He walked" not "He proceeded." "She wept" not "She expressed her grief."
Poetic only in rhythm, never in vocabulary.

== YOUR TASK ==

You will receive David Flip's brief — the lesson, metaphor, characters, and gut-punch
he wants. Your job is to craft this into a proper parable that could sit alongside
the Prodigal Son or the Good Samaritan without embarrassment.

Then format it as a comic script.

== ART STYLE FOR IMAGE PROMPTS ==

{art_style}

Every image prompt must include the full art style. Be extremely specific about visual
details: character poses, expressions, lighting, background elements, colour palette.
The image generator has NO memory — each prompt must be completely self-contained.

For ANY recurring character, describe them with EXACT same physical traits in every panel:
hair colour/style, clothing, age, distinguishing features. Create a character brief
internally and copy it into every panel prompt where they appear.

== JSON OUTPUT FORMAT ==

CRITICAL: Return ONLY the JSON object below. No preamble, no commentary, no explanation,
no "let me think about this", no markdown fences. Start your response with {{ and end with }}.

{{
  "title": "The Parable Title",
  "synopsis": "One-sentence summary",
  "parable_text": "The full parable as prose (250-400 words). This is the actual story text that will be used for narration.",
  "panels": [
    {{
      "panel_number": 1,
      "image_prompt": "Extremely detailed image description with full art style, character descriptions, scene, lighting, mood, composition. Self-contained.",
      "dialogue": [
        {{"speaker": "Character Name", "text": "What they say", "style": "normal"}}
      ],
      "narration": "Caption box text — use sparingly, only for David's brief poetic observations. NOT for explaining what's happening.",
      "camera": "wide_shot",
      "panel_type": "wide",
      "mood": "contemplative"
    }}
  ]
}}

CAMERA: wide_shot, medium_shot, close_up, extreme_close_up, birds_eye, low_angle, over_shoulder
PANEL TYPE: wide, standard, tall, splash
DIALOGUE STYLE: normal, whisper, shout, thought
MOOD: contemplative, urgent, hopeful, dark, knowing, direct

== CRITICAL RULES ==

1. The first 2-3 panels should have NO dialogue. Pure visual storytelling + sparse narration.
2. Dialogue enters at the crisis point (panel 4-6 typically).
3. The gut-punch line from David's brief MUST appear as spoken dialogue, not narration.
4. The final panel should land with maximum weight — question, silence, or proverb.
5. Narration caption boxes are David's voice. He is an observer, not an explainer.
   Good: "Some gifts remember every hand that touches them."
   Bad: "The fisherman realised the net was tracking his catch."
6. 6-8 panels total. Not more. Every panel must earn its place.
"""


class ScriptParser:
    """Generates structured comic scripts from parable themes via two-step process."""

    def __init__(self, model_router=None):
        self._model_router = model_router

    def _get_router(self):
        """Lazy-load model router."""
        if self._model_router is None:
            from core.model_router import ModelRouter
            self._model_router = ModelRouter()
        return self._model_router

    async def generate_script(
        self,
        theme: str,
        art_style: str = "",
        panel_count: int = 8,
        personality_prompt: str = "",
    ) -> ComicProject:
        """
        Generate a comic script from a parable theme using two-step process.

        Step 1: David Flip produces a brief (lesson, metaphor, characters, gut-punch)
        Step 2: Master Parable Writer crafts the story and comic panels

        Args:
            theme: The parable theme/description
            art_style: Override art style (uses default if empty)
            panel_count: Suggested panel count (6-8)
            personality_prompt: Optional additional personality overlay

        Returns:
            ComicProject with populated panels (no images yet)
        """
        router = self._get_router()

        if not art_style:
            art_style = ComicProject(title="", theme_id="").art_style

        # === Step 1: David's Brief ===
        logger.info("Step 1: David Flip creating parable brief...")
        brief = await self._generate_brief(router, theme, personality_prompt)
        logger.info(f"Brief ready: {brief.get('title_suggestion', 'untitled')}")

        # === Step 2: Master Parable Writer ===
        logger.info("Step 2: Master Parable Writer crafting story...")
        project = await self._write_parable(
            router, brief, art_style, panel_count
        )

        return project

    async def _generate_brief(
        self, router, theme: str, personality_prompt: str = ""
    ) -> dict:
        """Step 1: David Flip generates the parable brief."""
        system = DAVID_BRIEF_PROMPT
        if personality_prompt:
            system = personality_prompt + "\n\n" + system

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"Create a parable brief for this theme:\n\n{theme}\n\n"
                f"Remember: the lesson must be FELT, not explained. "
                f"The metaphor must be concrete and everyday. "
                f"The gut-punch must haunt."
            )},
        ]

        model = router.select_model("content_generation")
        response = await router.invoke(model, messages, max_tokens=2048)
        raw = response["content"].strip()
        json_text = self._extract_json(raw)

        try:
            brief = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Brief JSON parse failed. Raw (first 500 chars):\n{raw[:500]}")
            raise RuntimeError(f"David's brief returned invalid JSON: {e}") from e

        logger.info(f"David's brief — Lesson: {brief.get('lesson', '')[:80]}")
        logger.info(f"  Gut-punch: {brief.get('gut_punch', '')[:80]}")
        logger.info(f"  Ending: {brief.get('ending_type', '')} — {brief.get('ending_line', '')[:60]}")

        return brief

    async def _write_parable(
        self, router, brief: dict, art_style: str, panel_count: int
    ) -> ComicProject:
        """Step 2: Master Parable Writer crafts the story from David's brief."""
        system = PARABLE_WRITER_PROMPT.format(art_style=art_style)

        # Format David's brief for the writer
        brief_text = (
            f"== DAVID FLIP'S BRIEF ==\n\n"
            f"TITLE SUGGESTION: {brief.get('title_suggestion', 'Untitled')}\n"
            f"LESSON: {brief.get('lesson', '')}\n"
            f"METAPHOR: {brief.get('metaphor', '')}\n"
            f"SETTING: {brief.get('setting', '')}\n"
            f"FACTS TO EMBED: {brief.get('facts', '')}\n"
            f"GUT-PUNCH MOMENT: {brief.get('gut_punch', '')}\n"
            f"ENDING TYPE: {brief.get('ending_type', 'question')}\n"
            f"ENDING LINE: {brief.get('ending_line', '')}\n\n"
            f"CHARACTERS:\n"
        )
        for char in brief.get("characters", []):
            brief_text += (
                f"  - {char.get('name', '?')} ({char.get('role', '?')}): "
                f"{char.get('description', '')} — wants: {char.get('want', '')}\n"
            )

        brief_text += (
            f"\nWrite a {panel_count}-panel comic script. "
            f"The parable text should be 250-400 words. "
            f"Craft it like a Bible parable — Ground, Escalate, Turn, Land. "
            f"Return ONLY the JSON object, starting with {{ — no preamble."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": brief_text},
        ]

        model = router.select_model("content_generation")
        response = await router.invoke(model, messages, max_tokens=4096)
        raw = response["content"].strip()
        json_text = self._extract_json(raw)

        try:
            script_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed. Raw response (first 500 chars):\n{raw[:500]}")
            logger.error(f"Extracted JSON (first 500 chars):\n{json_text[:500]}")
            raise RuntimeError(f"Parable writer returned invalid JSON: {e}") from e

        # Build ComicProject
        project = ComicProject(
            title=script_data.get("title", brief.get("title_suggestion", "Untitled")),
            theme_id=self._slugify(script_data.get("title", "untitled")),
            synopsis=script_data.get("synopsis", ""),
            art_style=art_style,
        )

        # Store the full parable prose text
        project.parable_text = script_data.get("parable_text", "")

        for panel_data in script_data.get("panels", []):
            panel = Panel(
                panel_number=panel_data["panel_number"],
                image_prompt=panel_data["image_prompt"],
                dialogue=panel_data.get("dialogue", []),
                narration=panel_data.get("narration", ""),
                camera=self._parse_camera(panel_data.get("camera", "medium_shot")),
                panel_type=self._parse_panel_type(panel_data.get("panel_type", "standard")),
                mood=panel_data.get("mood", "contemplative"),
            )
            project.panels.append(panel)

        # Cost for both steps
        cost = self._estimate_cost(response.get("usage", {}), model)
        project.total_cost += cost
        project.log(f"Script generated (2-step): {len(project.panels)} panels, cost ~${cost:.4f}")

        logger.info(f"Parable ready: '{project.title}' — {len(project.panels)} panels")
        if project.parable_text:
            word_count = len(project.parable_text.split())
            logger.info(f"Parable text: {word_count} words")

        return project

    def _extract_json(self, text: str) -> str:
        """Extract JSON from model response, handling markdown fences, preamble, and control chars."""
        # Strip markdown code fences
        if "```json" in text:
            text = text.split("```json", 1)[1]
            text = text.rsplit("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1]
            text = text.rsplit("```", 1)[0]
        else:
            # Find first { and last } — handles preamble text before JSON
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                text = text[first_brace:last_brace + 1]

        text = text.strip()

        # Fix control characters inside JSON string values (newlines, tabs)
        # Replace literal newlines inside strings with \n escape
        import re
        # Replace actual newlines that are inside JSON string values
        # Strategy: replace all bare newlines with \\n, then fix the structural ones back
        lines = text.split("\n")
        text = "\n".join(lines)  # Normalize line endings

        # Try parsing with strict=False first (allows control chars in strings)
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Fallback: sanitize control characters inside string values
        # Replace problematic chars but preserve JSON structure
        cleaned = ""
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                cleaned += ch
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                cleaned += ch
                continue
            if ch == '"':
                in_string = not in_string
                cleaned += ch
                continue
            if in_string and ch in ("\n", "\r", "\t"):
                # Replace control chars inside strings with safe equivalents
                if ch == "\n":
                    cleaned += "\\n"
                elif ch == "\r":
                    cleaned += ""
                elif ch == "\t":
                    cleaned += "\\t"
            else:
                cleaned += ch

        return cleaned

    def _parse_camera(self, value: str) -> CameraHint:
        """Parse camera hint from string."""
        try:
            return CameraHint(value)
        except ValueError:
            return CameraHint.MEDIUM_SHOT

    def _parse_panel_type(self, value: str) -> PanelType:
        """Parse panel type from string."""
        try:
            return PanelType(value)
        except ValueError:
            return PanelType.STANDARD

    def _slugify(self, text: str) -> str:
        """Convert title to a URL/filesystem-safe slug."""
        import re
        slug = text.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        return slug.strip("_")[:60]

    def _estimate_cost(self, usage: dict, model) -> float:
        """Estimate API cost from token usage."""
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost = (input_tokens * model.cost_in + output_tokens * model.cost_out) / 1_000_000
        return cost
