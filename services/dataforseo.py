"""
DataForSEO API Client
Handles news scraping with batch optimization
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import os


class DataForSEOClient:
    def __init__(self):
        self.base_url = "https://api.dataforseo.com/v3"
        self.login = os.getenv("DATAFORSEO_LOGIN")
        self.password = os.getenv("DATAFORSEO_PASSWORD")

        if not self.login or not self.password:
            raise ValueError("DataForSEO credentials not configured")

    def search_news(
        self,
        keywords: List[str],
        market: str = "IT",
        days_back: int = 7,
        max_results: int = 100
    ) -> Dict:
        """
        Batch search for multiple keywords

        Args:
            keywords: List of search terms
            market: Country code (IT, US, UK, DE, FR, ES)
            days_back: How many days to look back
            max_results: Max results per query

        Returns:
            {
                'articles': List[Dict],
                'api_calls': int,
                'cost_usd': float
            }
        """
        location_map = {
            'IT': 2380,
            'US': 2840,
            'UK': 2826,
            'DE': 2276,
            'FR': 2250,
            'ES': 2724
        }

        language_map = {
            'IT': 'it',
            'US': 'en',
            'UK': 'en',
            'DE': 'de',
            'FR': 'fr',
            'ES': 'es'
        }

        # Combine keywords with OR for single query
        # This reduces API calls from N to 1
        combined_query = " OR ".join([f'"{kw}"' for kw in keywords])

        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        payload = [{
            "keyword": combined_query,
            "location_code": location_map.get(market, 2380),
            "language_code": language_map.get(market, 'it'),
            "depth": max_results,
            "date_from": date_from
        }]

        try:
            response = requests.post(
                f"{self.base_url}/serp/google/news/live/advanced",
                json=payload,
                auth=(self.login, self.password),
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            articles = []

            # Parse response
            for task in data.get('tasks', []):
                for result in task.get('result', []):
                    for item in result.get('items', []):
                        articles.append({
                            'url': item.get('url'),
                            'title': item.get('title'),
                            'source': item.get('source'),
                            'published_at': item.get('date'),
                            'snippet': item.get('snippet', ''),
                            'type': item.get('type', 'news')
                        })

            # Cost calculation: ~$0.10 per request
            api_calls = 1
            cost_usd = api_calls * 0.10

            return {
                'articles': articles,
                'api_calls': api_calls,
                'cost_usd': cost_usd,
                'success': True
            }

        except requests.exceptions.RequestException as e:
            return {
                'articles': [],
                'api_calls': 0,
                'cost_usd': 0,
                'success': False,
                'error': str(e)
            }

    def get_article_content(self, url: str) -> Optional[Dict]:
        """
        Fetch full article content (use sparingly, costs extra)

        Args:
            url: Article URL

        Returns:
            {'content': str, 'title': str} or None
        """
        payload = [{
            "url": url,
            "enable_javascript": True
        }]

        try:
            response = requests.post(
                f"{self.base_url}/on_page/content_parsing/live",
                json=payload,
                auth=(self.login, self.password),
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            result = data.get('tasks', [{}])[0].get('result', [{}])[0]
            items = result.get('items', [{}])[0]

            return {
                'content': items.get('content', ''),
                'title': items.get('title', '')
            }

        except Exception:
            return None
