"""
Research Agent - David's Intelligence Network

Autonomous agent that:
1. Scrapes multiple sources daily (GitHub, YouTube, Reddit, RSS)
2. Evaluates content against David's goals
3. Takes appropriate actions (alert, task, content, knowledge)
4. Sends daily digest at 6am UAE time
"""

from .agent import ResearchAgent
from .knowledge_store import KnowledgeStore
from .evaluator import GoalEvaluator
from .action_router import ActionRouter

__all__ = ["ResearchAgent", "KnowledgeStore", "GoalEvaluator", "ActionRouter"]
