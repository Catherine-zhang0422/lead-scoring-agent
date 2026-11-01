import json
from typing import Any, Dict
from agent.models import LeadRecord, ResearchStatus, WebsiteStatus, AmazonPresence, AmazonRelationship, Product, EvidenceItem
from agent.searcher import BaseSearchAdapter, FixtureSearchAdapter, SerpApiSearchAdapter
from agent.providers import BaseLLMProvider


class BrandResearcher:
    def __init__(self, searcher: BaseSearchAdapter, llm: BaseLLMProvider):
        self.searcher = searcher
        self.llm = llm

    def research_brand(self, brand_info: Dict[str, Any]) -> LeadRecord:
        brand_name = brand_info["brand"]
        category = brand_info.get("category", "unknown")
        input_source = brand_info.get("source_url", "direct_input")
        provided_website = brand_info.get("website")

        try:
            search_result = self.searcher.search(brand_name, category)
            
            website = provided_website or search_result.get("website")
            website_status = WebsiteStatus(search_result.get("website_status", "unknown"))
            has_ecommerce = bool(search_result.get("has_ecommerce_channel", False))
            amazon_url = search_result.get("amazon_url")
            amazon_presence = AmazonPresence(search_result.get("amazon_presence", "unknown"))
            amazon_relationship = AmazonRelationship(search_result.get("amazon_relationship", "unknown"))
            
            resolved_category = search_result.get("category") if search_result.get("category") and search_result.get("category") != "unknown" else category
            
            products = []
            for p in search_result.get("representative_products", []):
                products.append(Product(
                    name=p.get("name", "Representative Product"),
                    url=p.get("url"),
                    price=p.get("price"),
                    currency=p.get("currency", "GBP"),
                    evidence_id=p.get("evidence_id")
                ))

            evidence = []
            for e in search_result.get("evidence", []):
                evidence.append(EvidenceItem(
                    id=e.get("id", "ev_default"),
                    source_url=e.get("source_url", website or "https://example.com"),
                    summary=e.get("summary", "Evidence collected."),
                    timestamp=e.get("timestamp", "2026-11-01T12:00:00Z")
                ))

            research_status = ResearchStatus(search_result.get("research_status", "success"))
            warnings = search_result.get("warnings", [])

            if not website and research_status != ResearchStatus.FAILED:
                research_status = ResearchStatus.PARTIAL
                warnings.append("Official website could not be verified.")

            return LeadRecord(
                brand=brand_name,
                input_source=input_source,
                website=website,
                website_status=website_status,
                has_ecommerce_channel=has_ecommerce,
                amazon_url=amazon_url,
                amazon_presence=amazon_presence,
                amazon_relationship=amazon_relationship,
                category=resolved_category,
                representative_products=products,
                price_tier="unknown",
                price_basis="Pending price tier calculation",
                evidence=evidence,
                research_status=research_status,
                warnings=warnings
            )

        except Exception as e:
            return LeadRecord(
                brand=brand_name,
                input_source=input_source,
                website=provided_website,
                website_status=WebsiteStatus.ERROR,
                has_ecommerce_channel=False,
                category=category,
                research_status=ResearchStatus.FAILED,
                warnings=[f"Research exception encountered: {str(e)}"]
            )
