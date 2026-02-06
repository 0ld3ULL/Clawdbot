"""
David PIP Video Editor

Creates engaging videos with David in picture-in-picture corner,
B-roll as main content, and occasional full-screen David cuts.
"""

from .editor import DavidPIPEditor
from .broll_matcher import BRollMatcher

__all__ = ["DavidPIPEditor", "BRollMatcher"]
