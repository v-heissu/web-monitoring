"""
Gemini AI Analysis Service
Handles sentiment, topic extraction, and suggestions
"""

import google.generativeai as genai
from typing import List, Dict
import os
import json


class GeminiAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def batch_analyze_articles(
        self,
        articles: List[Dict],
        brand: str,
        batch_size: int = 20
    ) -> List[Dict]:
        """
        Batch analyze articles for sentiment, topics, entities

        Args:
            articles: List of articles with title + snippet
            brand: Brand name for context
            batch_size: Articles per API call

        Returns:
            Analyzed articles with AI fields added
        """
        analyzed = []

        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]

            prompt = f"""Analyze these news articles for brand monitoring of "{brand}".

For EACH article, return a JSON object with:
- sentiment: "positive", "negative", or "neutral"
- sentiment_score: float from -1.0 (very negative) to +1.0 (very positive)
- topics: array of 2-3 main topics/themes
- entities: object with arrays: {{"people": [], "organizations": [], "locations": []}}
- summary: 1-2 sentence summary in Italian
- relevance_score: 0-100 indicating relevance to {brand}

Articles to analyze:
{json.dumps([{'id': idx, 'title': a.get('title', ''), 'snippet': a.get('snippet', '')} for idx, a in enumerate(batch)], ensure_ascii=False, indent=2)}

Return ONLY a valid JSON array with {len(batch)} objects, no markdown, no explanation."""

            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': 0.3,
                        'top_p': 0.8,
                        'max_output_tokens': 8000
                    }
                )

                # Clean response
                text = response.text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()

                results = json.loads(text)

                # Merge with original articles
                for idx, result in enumerate(results):
                    if idx < len(batch):
                        analyzed.append({
                            **batch[idx],
                            'sentiment': result.get('sentiment', 'neutral'),
                            'sentiment_score': float(result.get('sentiment_score', 0)),
                            'topics': result.get('topics', []),
                            'entities': result.get('entities', {}),
                            'summary': result.get('summary', batch[idx].get('snippet', '')[:200]),
                            'relevance_score': float(result.get('relevance_score', 50))
                        })

            except Exception as e:
                print(f"Gemini analysis error: {e}")
                # Fallback: neutral analysis
                for article in batch:
                    analyzed.append({
                        **article,
                        'sentiment': 'neutral',
                        'sentiment_score': 0.0,
                        'topics': [],
                        'entities': {},
                        'summary': article.get('snippet', '')[:200],
                        'relevance_score': 50.0
                    })

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
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            if text.startswith('```json'):
                text = text[7:]
            if text.endswith('```'):
                text = text[:-3]

            return json.loads(text.strip())

        except Exception as e:
            print(f"Suggestion error: {e}")
            return {
                'competitors': [],
                'keywords': [],
                'portals': []
            }
