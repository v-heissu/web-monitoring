"""
Gemini AI Analysis Service
Handles sentiment, topic extraction, and suggestions
Memory-optimized for Railway workers
"""

import google.generativeai as genai
from typing import List, Dict, Callable, Optional
import os
import json
import gc
import time


class GeminiAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        genai.configure(api_key=api_key)
        self._model_name = 'gemini-2.0-flash-exp'
        # Don't hold model in memory - create per call
        self.model = None

    def _get_model(self):
        """Get or create model instance"""
        if self.model is None:
            self.model = genai.GenerativeModel(self._model_name)
        return self.model

    def _release_model(self):
        """Release model to free memory"""
        self.model = None
        gc.collect()

    def analyze_single_article(self, article: Dict, brand: str) -> Dict:
        """
        Analyze a single article - memory efficient version
        """
        prompt = f"""Analyze this news article for brand "{brand}".

Return JSON with:
- sentiment: "positive", "negative", or "neutral"
- sentiment_score: float -1.0 to +1.0
- topics: array of 2-3 topics
- entities: {{"people": [], "organizations": [], "locations": []}}
- summary: 1 sentence summary in Italian
- relevance_score: 0-100

Article:
Title: {article.get('title', '')[:200]}
Snippet: {article.get('snippet', '')[:300]}

Return ONLY valid JSON, no markdown."""

        try:
            model = self._get_model()
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'top_p': 0.8,
                    'max_output_tokens': 500  # Minimal for single article
                }
            )

            text = response.text.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)

            analyzed = {
                **article,
                'sentiment': result.get('sentiment', 'neutral'),
                'sentiment_score': float(result.get('sentiment_score', 0)),
                'topics': result.get('topics', []),
                'entities': result.get('entities', {}),
                'summary': result.get('summary', article.get('snippet', '')[:200]),
                'relevance_score': float(result.get('relevance_score', 50))
            }

            # Cleanup
            del response, text, result
            return analyzed

        except Exception as e:
            print(f"Gemini single analysis error: {e}")
            return {
                **article,
                'sentiment': 'neutral',
                'sentiment_score': 0.0,
                'topics': [],
                'entities': {},
                'summary': article.get('snippet', '')[:200],
                'relevance_score': 50.0
            }

    def batch_analyze_articles(
        self,
        articles: List[Dict],
        brand: str,
        batch_size: int = 1,  # Process one at a time for memory safety
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Dict]:
        """
        Analyze articles one by one for memory safety

        Args:
            articles: List of articles with title + snippet
            brand: Brand name for context
            batch_size: Ignored, always processes one at a time
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Analyzed articles with AI fields added
        """
        analyzed = []
        total = len(articles)

        # Force garbage collection before starting
        gc.collect()

        for i, article in enumerate(articles):
            # Progress callback
            if progress_callback:
                progress_callback(i + 1, total)

            # Analyze single article
            result = self.analyze_single_article(article, brand)
            analyzed.append(result)

            # Release model and collect garbage after EVERY article
            self._release_model()

            # Small delay to avoid rate limiting
            time.sleep(0.3)

        return analyzed

    def suggest_competitors_keywords(
        self,
        brand: str,
        industry: str,
        market: str = 'IT'
    ) -> Dict:
        """
        AI-powered onboarding: suggest competitors and keywords

        Args:
            brand: Brand name
            industry: Industry/sector
            market: Market code

        Returns:
            {
                'competitors': List[str],
                'keywords': List[str],
                'portals': List[Dict]
            }
        """
        prompt = f"""For a brand monitoring project in {market}:

Brand: {brand}
Industry: {industry}

Provide:
1. Top 5 direct competitors in the same market
2. 10 relevant Italian keywords for news monitoring (mix of brand terms, industry terms, trends)
3. 5 authoritative Italian news sources/portals for this industry

Return ONLY valid JSON:
{{
  "competitors": ["Company1", "Company2", "Company3", "Company4", "Company5"],
  "keywords": ["keyword1", "keyword2", ..., "keyword10"],
  "portals": [
    {{"name": "Portal Name", "domain": "example.com", "description": "Short description"}},
    ...
  ]
}}

No markdown, no explanation."""

        try:
            model = self._get_model()
            response = model.generate_content(prompt)
            text = response.text.strip()

            if text.startswith('```json'):
                text = text[7:]
            if text.endswith('```'):
                text = text[:-3]

            result = json.loads(text.strip())
            self._release_model()
            return result

        except Exception as e:
            print(f"Suggestion error: {e}")
            self._release_model()
            return {
                'competitors': [],
                'keywords': [],
                'portals': []
            }
