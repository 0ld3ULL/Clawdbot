"""
Occy Agent — Main orchestrator for autonomous video production.

Ties together all Occy subsystems:
- FocalBrowser: browser automation for Focal ML
- OccyLearner: systematic feature exploration
- OccyProducer: job-driven video production pipeline
- OccyReviewer: quality assessment via Gemini
- KnowledgeStore: permanent knowledge base
- EventStore: event memory with decay

This agent runs independently on the D computer (ASUS ROG laptop).
It does NOT need the VPS, Telegram bot, or Twitter tool from main.py.
It shares safety infrastructure (KillSwitch, AuditLog, ApprovalQueue).
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from core.audit_log import AuditLog
from core.kill_switch import KillSwitch
from core.memory.knowledge_store import KnowledgeStore
from core.memory.event_store import EventStore
from core.token_budget import TokenBudgetManager
from personality.occy import OccyPersonality

logger = logging.getLogger(__name__)


class OccyAgent:
    """
    Main orchestrator for Occy — autonomous video production specialist.

    Lazy-loads sub-components on first use. Can operate in three modes:
    - Exploration: learning Focal ML features systematically
    - Production: executing video production jobs
    - Idle: waiting for commands (checking job queue periodically)
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        audit_log: AuditLog,
        token_budget: TokenBudgetManager,
        model_router=None,
        approval_queue=None,
        headless: bool = True,
        llm_provider: str = "gemini",
    ):
        # Safety infrastructure (shared with main system)
        self.kill_switch = kill_switch
        self.audit_log = audit_log
        self.token_budget = token_budget
        self.model_router = model_router
        self.approval_queue = approval_queue
        self._llm_provider = llm_provider

        # Personality
        self.personality = OccyPersonality()

        # Knowledge stores (separate DBs from David's)
        self.knowledge = KnowledgeStore(db_path=Path("data/occy_knowledge.db"))
        self.events = EventStore(db_path=Path("data/occy_events.db"))

        # Sub-components (lazy-loaded)
        self._browser = None
        self._learner = None
        self._producer = None
        self._reviewer = None
        self._headless = headless

        # State
        self._running = False
        self._mode = "idle"  # idle / exploring / producing

        logger.info(f"{self.personality.name} ({self.personality.role}) initialized")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> bool:
        """
        Start Occy agent.

        Launches browser and verifies Focal ML access.
        Returns True if ready to operate.
        """
        if self.kill_switch.is_active:
            logger.warning("Kill switch active — Occy will not start")
            return False

        logger.info("Starting Occy agent...")

        # Start browser
        browser = await self._get_browser()
        if not browser:
            logger.error("Failed to start browser")
            return False

        # Check Focal login
        logged_in = await browser.check_login()
        if not logged_in:
            if self._headless:
                logger.error(
                    "Not logged in to Focal ML. Run with --visible flag "
                    "and log in manually first."
                )
                return False
            else:
                logger.warning(
                    "Not logged in to Focal ML. Browser is visible — "
                    "please log in manually. Occy will wait up to 5 minutes."
                )
                # Wait for manual login — poll every 30 seconds for 5 minutes
                for attempt in range(10):
                    logger.info(
                        f"Waiting for manual login... "
                        f"({(attempt + 1) * 30}s / 300s)"
                    )
                    await asyncio.sleep(30)
                    logged_in = await browser.check_login()
                    if logged_in:
                        break

                if not logged_in:
                    logger.error(
                        "Login timeout — no manual login detected after 5 minutes. "
                        "Please run again and log in to Focal ML in the browser window."
                    )
                    return False

        self._running = True

        self.audit_log.log(
            "occy", "info", "system",
            "Occy agent started",
            details=f"mode={'headless' if self._headless else 'visible'}, login={'ok' if logged_in else 'pending'}",
        )

        # Record event
        self.events.add(
            title="Occy agent started",
            summary=f"Started in {'headless' if self._headless else 'visible'} mode",
            significance=3,
            category="system",
        )

        return True

    async def stop(self):
        """Graceful shutdown — save state and close browser."""
        logger.info("Stopping Occy agent...")
        self._running = False
        self._mode = "idle"

        if self._browser:
            await self._browser.stop()
            self._browser = None

        self.audit_log.log("occy", "info", "system", "Occy agent stopped")
        logger.info("Occy agent stopped")

    def get_status(self) -> dict:
        """Get current agent status."""
        status = {
            "agent": self.personality.name,
            "role": self.personality.role,
            "running": self._running,
            "mode": self._mode,
            "kill_switch": self.kill_switch.is_active,
            "browser_active": self._browser is not None and self._browser._running,
        }

        # Add knowledge stats
        status["knowledge"] = self.knowledge.get_stats()

        # Add learning progress if learner initialized
        if self._learner:
            status["learning_progress"] = self._learner.get_progress()

        # Add job queue if producer initialized
        if self._producer:
            status["job_queue"] = self._producer.get_queue_status()

        return status

    # ------------------------------------------------------------------
    # Sub-component access (lazy loading)
    # ------------------------------------------------------------------

    async def _get_browser(self):
        """Get or create the browser instance."""
        if self._browser is None:
            from agents.occy_browser import FocalBrowser
            self._browser = FocalBrowser(
                headless=self._headless,
                llm_provider=self._llm_provider,
            )
            success = await self._browser.start()
            if not success:
                self._browser = None
                return None
        return self._browser

    def _get_learner(self):
        """Get or create the learner instance."""
        if self._learner is None:
            from agents.occy_learner import OccyLearner
            self._learner = OccyLearner(
                browser=self._browser,
                knowledge_store=self.knowledge,
                audit_log=self.audit_log,
                model_router=self.model_router,
            )
        return self._learner

    def _get_reviewer(self):
        """Get or create the reviewer instance."""
        if self._reviewer is None:
            from agents.occy_reviewer import OccyReviewer
            self._reviewer = OccyReviewer(knowledge_store=self.knowledge)
        return self._reviewer

    def _get_producer(self):
        """Get or create the producer instance."""
        if self._producer is None:
            from agents.occy_producer import OccyProducer
            self._producer = OccyProducer(
                browser=self._browser,
                reviewer=self._get_reviewer(),
                knowledge_store=self.knowledge,
                approval_queue=self.approval_queue,
                audit_log=self.audit_log,
            )
        return self._producer

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def run_exploration(self, duration_minutes: int = 30) -> dict:
        """
        Run an exploration session.

        Occy explores Focal ML features systematically for the given duration.
        """
        if self.kill_switch.is_active:
            return {"error": "Kill switch active"}

        if not self._running:
            return {"error": "Agent not started"}

        self._mode = "exploring"
        logger.info(f"Starting {duration_minutes}-minute exploration session")

        try:
            learner = self._get_learner()
            result = await learner.run_exploration_session(duration_minutes)

            self.events.add(
                title=f"Exploration session: {result['features_explored']} features",
                summary=(
                    f"Explored {result['features_explored']} features, "
                    f"added {result['knowledge_entries']} knowledge entries, "
                    f"used {result['total_credits']} credits"
                ),
                significance=4,
                category="learning",
            )

            return result

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            self.audit_log.log(
                "occy", "reject", "exploration",
                f"Exploration session failed: {e}",
                success=False,
            )
            return {"error": str(e)}
        finally:
            self._mode = "idle"

    async def submit_job(
        self,
        title: str,
        description: str = "",
        script: str = "",
        model: str = "auto",
        duration_seconds: int = 30,
    ) -> dict:
        """
        Submit a new video production job.

        Creates the job, generates a production plan, and submits
        for approval. Returns job details.
        """
        if self.kill_switch.is_active:
            return {"error": "Kill switch active"}

        producer = self._get_producer()

        # Create job
        job_id = producer.create_job(
            title=title,
            description=description,
            script=script,
            model=model,
            duration_seconds=duration_seconds,
        )

        # Create production plan
        plan = await producer.create_production_plan(job_id)

        # Submit for approval
        approval_id = await producer.submit_for_approval(job_id)

        return {
            "job_id": job_id,
            "approval_id": approval_id,
            "plan": plan,
            "status": "planned — awaiting approval",
        }

    async def execute_approved_job(self, job_id: int) -> dict:
        """
        Execute an approved production job.

        Full pipeline: produce → review → re-render if needed → deliver.
        """
        if self.kill_switch.is_active:
            return {"error": "Kill switch active"}

        if not self._running:
            return {"error": "Agent not started"}

        self._mode = "producing"
        logger.info(f"Executing production job #{job_id}")

        try:
            producer = self._get_producer()
            result = await producer.produce_video(job_id)

            # Record event
            if result["success"]:
                self.events.add(
                    title=f"Video delivered: job #{job_id}",
                    summary=(
                        f"Quality: {result['quality_score']:.1f}/10, "
                        f"Attempts: {result['attempts']}, "
                        f"Credits: {result['credits_used']}"
                    ),
                    significance=6,
                    category="production",
                )
            else:
                self.events.add(
                    title=f"Video production failed: job #{job_id}",
                    summary=result.get("error", "Unknown error"),
                    significance=5,
                    category="production",
                )

            return result

        except Exception as e:
            logger.error(f"Production failed: {e}")
            return {"error": str(e)}
        finally:
            self._mode = "idle"

    async def take_screenshot(self, name: str = "manual") -> str | None:
        """Take a screenshot of the current browser state."""
        browser = await self._get_browser()
        if browser:
            path = await browser.take_screenshot(name)
            return str(path) if path else None
        return None

    async def get_credit_balance(self) -> int | None:
        """Get current Focal ML credit balance."""
        if self._browser and self._browser._running:
            return await self._browser.get_credit_balance()
        return None

    def get_learning_progress(self) -> dict:
        """Get learning progress summary."""
        learner = self._get_learner()
        return learner.get_progress()

    def get_job_queue(self) -> dict:
        """Get job queue status."""
        producer = self._get_producer()
        return producer.get_queue_status()

    # ------------------------------------------------------------------
    # Command handler (for Telegram integration)
    # ------------------------------------------------------------------

    async def handle_command(self, command: str, args: str = "") -> str:
        """
        Handle commands from Telegram or other interfaces.

        Commands:
            status — Current agent status
            explore <minutes> — Start exploration session
            job <description> — Submit a new production job
            produce <job_id> — Execute an approved job
            screenshot — Take a screenshot
            credits — Check credit balance
            progress — Learning progress
            queue — Job queue status
        """
        command = command.lower().strip()

        if command == "status":
            status = self.get_status()
            return json.dumps(status, indent=2)

        elif command == "explore":
            minutes = int(args) if args.strip().isdigit() else 30
            result = await self.run_exploration(minutes)
            return json.dumps(result, indent=2)

        elif command == "job":
            if not args.strip():
                return "Usage: job <description of video to create>"
            result = await self.submit_job(title=args.strip()[:100], description=args.strip())
            return json.dumps(result, indent=2)

        elif command == "produce":
            if not args.strip().isdigit():
                return "Usage: produce <job_id>"
            result = await self.execute_approved_job(int(args.strip()))
            return json.dumps(result, indent=2)

        elif command == "screenshot":
            path = await self.take_screenshot(args.strip() or "manual")
            return f"Screenshot saved: {path}" if path else "Screenshot failed"

        elif command == "credits":
            balance = await self.get_credit_balance()
            return f"Credit balance: {balance}" if balance is not None else "Could not read balance"

        elif command == "progress":
            progress = self.get_learning_progress()
            return json.dumps(progress, indent=2)

        elif command == "queue":
            queue = self.get_job_queue()
            return json.dumps(queue, indent=2)

        else:
            return (
                "Occy commands:\n"
                "  status — Current agent status\n"
                "  explore [minutes] — Start exploration session\n"
                "  job <description> — Submit new video job\n"
                "  produce <job_id> — Execute approved job\n"
                "  screenshot [name] — Take screenshot\n"
                "  credits — Check Focal credit balance\n"
                "  progress — Learning progress\n"
                "  queue — Job queue status"
            )
