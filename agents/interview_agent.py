"""
Interview Agent - Manages the interview lifecycle.

Workflow:
1. create_interview(topic, expert_name) — LLM generates 3-5 questions,
   renders David asking each one via VideoCreator, saves to
   output/interviews/{id}/questions/
2. check_answers(interview_id) — checks if expert videos exist in answers/ folder
3. compose_final(interview_id) — calls InterviewCompositor, submits to approval queue

Human stays in control: all generation is operator-triggered,
final videos go through approval queue.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

INTERVIEWS_DIR = "output/interviews"


class InterviewAgent:
    """
    Manages the full interview lifecycle from question generation
    through final composition.
    """

    def __init__(self, approval_queue=None, personality=None, model_router=None):
        self.approval_queue = approval_queue
        self.personality = personality
        self._model_router = model_router
        self._video_creator = None
        self._compositor = None

        # Ensure interviews directory exists
        Path(INTERVIEWS_DIR).mkdir(parents=True, exist_ok=True)

        # Load interview index
        self._index_path = os.path.join(INTERVIEWS_DIR, "index.json")
        self._interviews = self._load_index()

    def _load_index(self) -> dict:
        """Load the interview tracking index."""
        if os.path.exists(self._index_path):
            try:
                with open(self._index_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_index(self):
        """Persist the interview tracking index."""
        with open(self._index_path, "w") as f:
            json.dump(self._interviews, f, indent=2)

    def _get_model_router(self):
        """Lazy-load model router."""
        if self._model_router is None:
            try:
                from core.model_router import ModelRouter
                self._model_router = ModelRouter()
            except Exception as e:
                logger.error(f"Failed to load model router: {e}")
        return self._model_router

    def _get_video_creator(self):
        """Lazy-load video creator."""
        if self._video_creator is None:
            try:
                from video_pipeline.video_creator import VideoCreator
                self._video_creator = VideoCreator()
            except Exception as e:
                logger.error(f"Failed to load video creator: {e}")
        return self._video_creator

    def _get_compositor(self):
        """Lazy-load interview compositor."""
        if self._compositor is None:
            try:
                from video_pipeline.interview_compositor import InterviewCompositor
                self._compositor = InterviewCompositor()
            except Exception as e:
                logger.error(f"Failed to load interview compositor: {e}")
        return self._compositor

    async def create_interview(
        self,
        topic: str,
        expert_name: str,
        num_questions: int = 3,
    ) -> dict:
        """
        Create a new interview: generate questions and render David clips.

        Args:
            topic: Interview topic
            expert_name: Name of the expert being interviewed
            num_questions: Number of questions to generate (3-5)

        Returns:
            dict with interview_id, questions, status
        """
        num_questions = max(3, min(5, num_questions))

        # Generate unique interview ID
        interview_id = datetime.now().strftime("%Y%m%d") + "_" + uuid.uuid4().hex[:6]

        # Create directory structure
        interview_dir = os.path.join(INTERVIEWS_DIR, interview_id)
        questions_dir = os.path.join(interview_dir, "questions")
        answers_dir = os.path.join(interview_dir, "answers")
        Path(questions_dir).mkdir(parents=True, exist_ok=True)
        Path(answers_dir).mkdir(parents=True, exist_ok=True)

        # Generate questions using LLM
        questions = await self._generate_questions(topic, expert_name, num_questions)
        if not questions:
            return {"error": "Failed to generate questions"}

        # Save interview metadata
        metadata = {
            "id": interview_id,
            "topic": topic,
            "expert_name": expert_name,
            "questions": questions,
            "status": "generating_clips",
            "created_at": datetime.now().isoformat(),
            "questions_dir": questions_dir,
            "answers_dir": answers_dir,
        }

        metadata_path = os.path.join(interview_dir, "metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Render David asking each question
        rendered = []
        video_creator = self._get_video_creator()
        if not video_creator:
            metadata["status"] = "error"
            metadata["error"] = "Video creator not available"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)
            return {"error": "Video creator not available", "interview_id": interview_id}

        for i, question in enumerate(questions, 1):
            try:
                output_path = os.path.join(questions_dir, f"q{i}.mp4")
                result = await video_creator.create_video(
                    script=question,
                    character_style="podcast",  # Side angle for interview feel
                    output_path=output_path,
                    auto_music=False,  # No music for interview questions
                )
                rendered.append({
                    "question_num": i,
                    "question": question,
                    "video_path": result["video_path"],
                })
                logger.info(f"Rendered question {i}/{len(questions)}: {question[:50]}...")
            except Exception as e:
                logger.error(f"Failed to render question {i}: {e}")
                rendered.append({
                    "question_num": i,
                    "question": question,
                    "error": str(e),
                })

        # Update metadata
        metadata["status"] = "awaiting_answers"
        metadata["rendered_questions"] = rendered
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Update index
        self._interviews[interview_id] = {
            "topic": topic,
            "expert_name": expert_name,
            "status": "awaiting_answers",
            "created_at": metadata["created_at"],
            "question_count": len(questions),
        }
        self._save_index()

        return {
            "interview_id": interview_id,
            "topic": topic,
            "expert_name": expert_name,
            "questions": questions,
            "rendered": rendered,
            "status": "awaiting_answers",
            "answers_dir": answers_dir,
        }

    async def _generate_questions(
        self, topic: str, expert_name: str, num_questions: int
    ) -> list[str]:
        """Generate interview questions using LLM."""
        router = self._get_model_router()
        if not router:
            return self._fallback_questions(topic, num_questions)

        # Build prompt using personality
        system_prompt = ""
        if self.personality and hasattr(self.personality, 'get_system_prompt'):
            system_prompt = self.personality.get_system_prompt("video_script")

        prompt = f"""{system_prompt}

You are David Flip, preparing to interview {expert_name} about {topic}.

Generate exactly {num_questions} interview questions. Each question should:
- Be conversational and direct (David's style)
- Be 1-2 sentences max (these will be spoken on camera)
- Progress from accessible to deeper/more provocative
- Feel natural, not scripted
- Use David's voice: direct, curious, slightly provocative

Return ONLY the questions, one per line, numbered 1-{num_questions}.
No other text."""

        try:
            response = await router.complete(
                prompt=prompt,
                model_preference="sonnet",
                max_tokens=500,
            )
            content = response.get("content", "").strip()

            # Parse numbered questions
            questions = []
            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Remove numbering (1., 1), Q1:, etc.)
                import re
                cleaned = re.sub(r"^(\d+[\.\)]\s*|Q\d+[:\s]*)", "", line).strip()
                if cleaned:
                    questions.append(cleaned)

            return questions[:num_questions]

        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return self._fallback_questions(topic, num_questions)

    def _fallback_questions(self, topic: str, num_questions: int) -> list[str]:
        """Fallback questions if LLM is unavailable."""
        fallbacks = [
            f"Let's talk about {topic}. What's the one thing most people get wrong about this?",
            f"When it comes to {topic} — — who benefits and who gets left behind?",
            f"If you had 60 seconds to explain why {topic} matters right now, what would you say?",
            f"What's the thing about {topic} that keeps you up at night?",
            f"Where do you see this going in the next 2-3 years? And should we be worried?",
        ]
        return fallbacks[:num_questions]

    def check_answers(self, interview_id: str) -> dict:
        """
        Check upload progress for expert answer videos.

        Returns status of each Q&A pair.
        """
        interview_dir = os.path.join(INTERVIEWS_DIR, interview_id)
        metadata_path = os.path.join(interview_dir, "metadata.json")

        if not os.path.exists(metadata_path):
            return {"error": f"Interview {interview_id} not found"}

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        compositor = self._get_compositor()
        if compositor:
            status = compositor.check_clip_pairs(
                metadata["questions_dir"],
                metadata["answers_dir"],
            )
        else:
            # Manual check
            questions_dir = Path(metadata["questions_dir"])
            answers_dir = Path(metadata["answers_dir"])
            q_count = len(list(questions_dir.glob("q*.mp4")))
            a_count = len(list(answers_dir.glob("a*.mp4")))
            status = {
                "total_questions": q_count,
                "total_answers": a_count,
                "complete_pairs": min(q_count, a_count),
                "ready_to_compose": a_count > 0,
                "all_complete": a_count >= q_count,
            }

        return {
            "interview_id": interview_id,
            "topic": metadata.get("topic", ""),
            "expert_name": metadata.get("expert_name", ""),
            "status": metadata.get("status", "unknown"),
            **status,
        }

    def get_answers_dir(self, interview_id: str) -> Optional[str]:
        """Get the answers directory for an interview (for file uploads)."""
        interview_dir = os.path.join(INTERVIEWS_DIR, interview_id)
        answers_dir = os.path.join(interview_dir, "answers")
        if os.path.isdir(answers_dir):
            return answers_dir
        return None

    async def compose_final(self, interview_id: str) -> dict:
        """
        Compose the final interview video and submit to approval queue.

        Requires at least one complete Q&A pair.
        """
        interview_dir = os.path.join(INTERVIEWS_DIR, interview_id)
        metadata_path = os.path.join(interview_dir, "metadata.json")

        if not os.path.exists(metadata_path):
            return {"error": f"Interview {interview_id} not found"}

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        compositor = self._get_compositor()
        if not compositor:
            return {"error": "Interview compositor not available"}

        # Check readiness
        status = compositor.check_clip_pairs(
            metadata["questions_dir"],
            metadata["answers_dir"],
        )
        if not status.get("ready_to_compose"):
            return {
                "error": "No complete Q&A pairs. Upload expert answer videos first.",
                "status": status,
            }

        # Compose
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            interview_dir,
            f"final_{timestamp}.mp4",
        )

        topic = metadata.get("topic", "Interview")
        expert_name = metadata.get("expert_name", "Expert")
        title = f"David Flip x {expert_name}: {topic}"

        result = await compositor.compose_interview(
            questions_dir=metadata["questions_dir"],
            answers_dir=metadata["answers_dir"],
            output_path=output_path,
            title=title,
            expert_name=expert_name,
        )

        if "error" in result:
            return result

        # Update metadata
        metadata["status"] = "composed"
        metadata["final_video"] = output_path
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Update index
        if interview_id in self._interviews:
            self._interviews[interview_id]["status"] = "composed"
            self._save_index()

        # Submit to approval queue
        approval_id = None
        if self.approval_queue:
            approval_id = self.approval_queue.submit(
                project_id="david-flip",
                agent_id="interview-agent",
                action_type="video_distribute",
                action_data={
                    "script": f"Interview: {title}",
                    "video_path": output_path,
                    "mood": "contemplative",
                    "pillar": 2,
                    "theme_title": title,
                    "category": "interview",
                },
                context_summary=f"Interview video: {title} ({status['complete_pairs']} Q&A pairs)",
            )
            logger.info(f"Interview video submitted for approval: #{approval_id}")

        return {
            "interview_id": interview_id,
            "output_path": output_path,
            "approval_id": approval_id,
            "qa_pairs": result.get("qa_pairs", 0),
            "duration": result.get("duration", 0),
        }

    def list_interviews(self) -> list[dict]:
        """List all interviews with their status."""
        # Reload index to catch any changes
        self._interviews = self._load_index()

        interviews = []
        for iid, info in self._interviews.items():
            interviews.append({
                "id": iid,
                "topic": info.get("topic", ""),
                "expert_name": info.get("expert_name", ""),
                "status": info.get("status", "unknown"),
                "created_at": info.get("created_at", ""),
                "question_count": info.get("question_count", 0),
            })

        # Sort by creation date, newest first
        interviews.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return interviews

    def save_answer_video(self, interview_id: str, file_data: bytes, filename: str) -> dict:
        """
        Save an uploaded answer video to the interview's answers directory.

        Auto-detects the next answer number or uses filename hint.
        """
        answers_dir = self.get_answers_dir(interview_id)
        if not answers_dir:
            return {"error": f"Interview {interview_id} not found"}

        answers_path = Path(answers_dir)

        # Determine answer number
        existing = sorted(answers_path.glob("a*.mp4"))
        next_num = len(existing) + 1

        # Check if filename hints at a number (e.g., "a2.mp4", "answer_3.mp4")
        import re
        num_match = re.search(r"(\d+)", filename)
        if num_match:
            hinted_num = int(num_match.group(1))
            if 1 <= hinted_num <= 10:
                next_num = hinted_num

        output_filename = f"a{next_num}.mp4"
        output_path = os.path.join(answers_dir, output_filename)

        with open(output_path, "wb") as f:
            f.write(file_data)

        logger.info(f"Saved answer video: {output_path}")

        return {
            "saved_as": output_filename,
            "path": output_path,
            "answer_num": next_num,
            "interview_id": interview_id,
        }
