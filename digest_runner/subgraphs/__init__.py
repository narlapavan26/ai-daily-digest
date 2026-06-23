"""
digest_runner/subgraphs/__init__.py
====================================
Exports all implemented source subgraphs.

    from digest_runner.subgraphs import (
        RssSubgraph, ArxivSubgraph, GithubSubgraph, HackerNewsSubgraph,
        HuggingFaceSubgraph, RedditSubgraph, StackOverflowSubgraph,
    )
"""

from .base import BaseSubgraph, enrich_normalized_items, get_instructor_client  # noqa: F401
from .rss_subgraph import RssSubgraph                       # noqa: F401
from .arxiv_subgraph import ArxivSubgraph                   # noqa: F401
from .github_subgraph import GithubSubgraph                 # noqa: F401
from .hackernews_subgraph import HackerNewsSubgraph         # noqa: F401
from .huggingface_subgraph import HuggingFaceSubgraph       # noqa: F401
from .reddit_subgraph import RedditSubgraph                 # noqa: F401
from .stackoverflow_subgraph import StackOverflowSubgraph   # noqa: F401

__all__ = [
    "BaseSubgraph",
    "RssSubgraph",
    "ArxivSubgraph",
    "GithubSubgraph",
    "HackerNewsSubgraph",
    "HuggingFaceSubgraph",
    "RedditSubgraph",
    "StackOverflowSubgraph",
]
