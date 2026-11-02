import json
import os
import requests
from typing import Any, Dict, List, Optional


class BaseSearchAdapter:
    def search(self, brand_name: str, category: str) -> Dict[str, Any]:
        raise NotImplementedError


class FixtureSearchAdapter(BaseSearchAdapter):
    is_demo = True

    def __init__(self, fixture_path="sample_data/fixtures/mock_responses.json"):
    def __init__(self, fixture_path: str = "sample_data/fixtures/mock_responses.json"):
        self.fixture_path = fixture_path
        self.data = self._load_fixtures()

    def _load_fixtures(self) -> Dict[str, Any]:
        if os.path.exists(self.fixture_path):
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def search(self, brand_name: str, category: str) -> Dict[str, Any]:
        if brand_name in self.data:
            return self.data[brand_name]
        
        return {
            "website": f"https://{brand_name.lower().replace(' ', '')}-demo.example.com",
            "website_status": "active",
            "has_ecommerce_channel": True,
            "amazon_url": f"https://www.amazon.co.uk/stores/{brand_name.replace(' ', '')}/demo",
            "amazon_presence": "official_store",
            "amazon_relationship": "verified_official",
            "category": category if category != "unknown" else "Fashion",
            "representative_products": [
                {"name": f"{brand_name} Signature Item", "url": f"https://{brand_name.lower().replace(' ', '')}-demo.example.com/item1", "price": 49.99, "currency": "GBP", "evidence_id": f"ev_{brand_name.lower().replace(' ', '_')}_1"}
            ],
            "evidence": [
                {"id": f"ev_{brand_name.lower().replace(' ', '_')}_1", "source_url": f"https://{brand_name.lower().replace(' ', '')}-demo.example.com/item1", "summary": "Synthetic demo evidence for offline presentation.", "timestamp": "2026-11-01T12:00:00Z"}
            ],
            "research_status": "success",
            "warnings": ["Generated via demo fixture adapter."]
        }


class SerpApiSearchAdapter(BaseSearchAdapter):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SEARCH_API_KEY")
        if not self.api_key:
            raise ValueError("SEARCH_API_KEY is required for live search mode.")

    def search(self, brand_name: str, category: str) -> Dict[str, Any]:
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google",
            "q": f"{brand_name} UK retail official website store amazon.co.uk",
            "api_key": self.api_key,
            "gl": "uk",
            "hl": "en"
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                return {
                    "website": None,
                    "website_status": "error",
                    "has_ecommerce_channel": False,
                    "amazon_url": None,
                    "amazon_presence": "unknown",
                    "amazon_relationship": "unknown",
                    "category": category,
                    "representative_products": [],
                    "evidence": [],
                    "research_status": "failed",
                    "warnings": [f"Search API returned status code {resp.status_code}"]
                }
            
            data = resp.json()
            organic = data.get("organic_results", [])
            
            official_site = None
            amazon_url = None
            evidence = []
            
            for idx, item in enumerate(organic[:5]):
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                title = item.get("title", "")
                ev_id = f"ev_search_{idx+1}"
                evidence.append({
                    "id": ev_id,
                    "source_url": link,
                    "summary": f"Search result [{title}]: {snippet[:150]}",
                    "timestamp": "2026-11-01T12:00:00Z"
                })
                
                if not official_site and "amazon.co.uk" not in link and any(term in link.lower() for term in [brand_name.lower().replace(" ", ""), "official"]):
                    official_site = link
                if not amazon_url and "amazon.co.uk/stores" in link:
                    amazon_url = link

            if not official_site and organic:
                official_site = organic[0].get("link")

            return {
                "website": official_site,
                "website_status": "active" if official_site else "unknown",
                "has_ecommerce_channel": bool(official_site),
                "amazon_url": amazon_url,
                "amazon_presence": "official_store" if amazon_url else ("product_listing" if amazon_url else "none"),
                "amazon_relationship": "verified_official" if amazon_url else "none",
                "category": category,
                "representative_products": [],
                "evidence": evidence,
                "research_status": "success" if official_site else "partial",
                "warnings": []
            }
        except Exception as e:
            return {
                "website": None,
                "website_status": "error",
                "has_ecommerce_channel": False,
                "amazon_url": None,
                "amazon_presence": "unknown",
                "amazon_relationship": "unknown",
                "category": category,
                "representative_products": [],
                "evidence": [],
                "research_status": "failed",
                "warnings": [f"Live search exception: {str(e)}"]
            }
