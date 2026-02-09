"""
GitHub Trending Scraper - Catches new AI/agent projects before they're on our watch list.

Scrapes the GitHub trending page for repos matching relevance keywords.
Frequency: WARM tier (every 8-12 hours).
"""

import logging
import re
from datetime import datetime
from typing import List

import httpx
import yaml

from ..knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"


class GitHubTrendingScraper:
    """Scrapes GitHub trending page for relevant new repos."""

    name = "github_trending"
    frequency = "warm"

    def __init__(self):
        self.config = self._load_config()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.keywords = [k.lower() for k in self.config.get("relevance_keywords", [])]
        self.min_stars = self.config.get("min_stars_today", 50)

    def _load_config(self) -> dict:
        """Load GitHub Trending configuration."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("sources", {}).get("github_trending", {})
        except Exception as e:
            logger.error(f"Failed to load GitHub Trending config: {e}")
            return {}

    async def scrape(self) -> List[ResearchItem]:
        """Scrape GitHub trending pages for relevant repos."""
        if not self.config.get("enabled", True):
            return []

        items = []
        seen_repos = set()
        languages = self.config.get("languages", ["", "python", "typescript"])

        for lang in languages:
            try:
                lang_items = await self._scrape_trending_page(lang, seen_repos)
                items.extend(lang_items)
            except Exception as e:
                logger.error(f"Error scraping trending/{lang}: {e}")

        logger.info(f"GitHub Trending found {len(items)} relevant repos")
        return items

    async def _scrape_trending_page(self, language: str,
                                     seen: set) -> List[ResearchItem]:
        """Scrape a single GitHub trending page."""
        items = []
        url = f"https://github.com/trending/{language}" if language else "https://github.com/trending"

        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                logger.warning(f"GitHub trending returned {response.status_code}")
                return items

            html = response.text
            repos = self._parse_trending_html(html)

            for repo in repos:
                repo_name = repo["name"]

                # Dedup across language pages
                if repo_name in seen:
                    continue
                seen.add(repo_name)

                # Filter by stars today
                if repo["stars_today"] < self.min_stars:
                    continue

                # Filter by keyword relevance
                search_text = f"{repo_name} {repo['description']}".lower()
                if self.keywords and not any(kw in search_text for kw in self.keywords):
                    continue

                content = (
                    f"{repo['description']}\n\n"
                    f"Language: {repo['language']}\n"
                    f"Total Stars: {repo['total_stars']}\n"
                    f"Stars Today: +{repo['stars_today']}\n"
                    f"Forks: {repo['forks']}"
                )

                items.append(ResearchItem(
                    source="github_trending",
                    source_id=f"trending:{repo_name}:{datetime.utcnow().strftime('%Y%m%d')}",
                    url=f"https://github.com/{repo_name}",
                    title=f"[Trending +{repo['stars_today']}] {repo_name}: {repo['description'][:80]}",
                    content=content,
                    published_at=datetime.utcnow(),
                ))

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error scraping trending: {e}")
        except Exception as e:
            logger.error(f"Error parsing trending page: {e}")

        return items

    def _parse_trending_html(self, html: str) -> List[dict]:
        """Parse GitHub trending HTML to extract repo data."""
        repos = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            for article in soup.select("article.Box-row"):
                try:
                    # Repo name (owner/name)
                    name_el = article.select_one("h2 a")
                    if not name_el:
                        continue
                    repo_name = name_el.get("href", "").strip("/")

                    # Description
                    desc_el = article.select_one("p")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    # Language
                    lang_el = article.select_one("[itemprop='programmingLanguage']")
                    language = lang_el.get_text(strip=True) if lang_el else "Unknown"

                    # Stars today (look for "stars today" text)
                    stars_today = 0
                    stars_today_el = article.select_one("span.d-inline-block.float-sm-right")
                    if stars_today_el:
                        stars_text = stars_today_el.get_text(strip=True)
                        match = re.search(r'([\d,]+)\s+stars?\s+today', stars_text)
                        if match:
                            stars_today = int(match.group(1).replace(",", ""))

                    # Total stars and forks from link elements
                    total_stars = 0
                    forks = 0
                    link_els = article.select("a.Link--muted")
                    for link in link_els:
                        href = link.get("href", "")
                        text = link.get_text(strip=True).replace(",", "")
                        if "/stargazers" in href and text.isdigit():
                            total_stars = int(text)
                        elif "/forks" in href and text.isdigit():
                            forks = int(text)

                    repos.append({
                        "name": repo_name,
                        "description": description,
                        "language": language,
                        "total_stars": total_stars,
                        "stars_today": stars_today,
                        "forks": forks,
                    })

                except Exception as e:
                    logger.debug(f"Error parsing repo article: {e}")
                    continue

        except ImportError:
            logger.error("beautifulsoup4 not installed. Run: pip install beautifulsoup4")
        except Exception as e:
            logger.error(f"Error parsing trending HTML: {e}")

        return repos

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
