"""
Research Agent - David's Intelligence Network

Autonomous agent that:
1. Scrapes multiple sources on tiered frequencies (hot/warm/daily)
2. Evaluates content against David's goals using dual rubrics + LLM fallback
3. Detects cross-source trends
4. Takes appropriate actions (alert, task, content, knowledge, watch)
5. Generates daily podcast script and newsletter
6. Sends daily digest at 6am UAE time
"""

from .agent import ResearchAgent
from .knowledge_store import KnowledgeStore
from .evaluator import GoalEvaluator
from .action_router import ActionRouter
from .trend_detector import TrendDetector
from .podcast_digest import PodcastDigestGenerator

__all__ = [
    "ResearchAgent", "KnowledgeStore", "GoalEvaluator", "ActionRouter",
    "TrendDetector", "PodcastDigestGenerator",
]
