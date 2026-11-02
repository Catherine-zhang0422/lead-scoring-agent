from datetime import datetime, timezone

from agent.models import (
    AmazonPresence,
    AmazonRelationship,
    LeadRecord,
    ResearchStatus,
    WebsiteStatus,
)


class BrandResearcher:
    """Research a brand and return a validated LeadRecord."""

    def __init__(self, searcher, llm):
        self.searcher = searcher
        self.llm = llm

    def research_brand(self, brand_info):
        brand = str(brand_info.get("brand", "")).strip()
        source = (
            brand_info.get("input_source")
            or brand_info.get("source_url")
            or "unknown"
        )
        category = brand_info.get("category") or "unknown"

        if not brand:
            raise ValueError("Brand name must not be empty.")

        try:
            result = self.searcher.search(brand, category)

            if not isinstance(result, dict):
                raise ValueError("Search adapter must return a dictionary.")

            # Identity and source always come from the input.
            payload = {
                **result,
                "brand": brand,
                "input_source": source,
                "researched_at": datetime.now(timezone.utc).isoformat(),
            }

            # Ignore fields outside the shared data model.
            payload = {
                key: value
                for key, value in payload.items()
                if key in LeadRecord.model_fields
            }

            lead = LeadRecord.model_validate(payload)

            # Search snippets alone do not verify a website or storefront.
            # Until live page verification is implemented, keep these
            # claims unknown and prevent unsupported positive scoring.
            is_demo = getattr(self.searcher, "is_demo", False)

            if not is_demo:
                lead.website_status = WebsiteStatus.UNKNOWN
                lead.has_ecommerce_channel = False
                lead.amazon_presence = AmazonPresence.UNKNOWN
                lead.amazon_relationship = AmazonRelationship.UNKNOWN
                lead.category = "unknown"
                lead.representative_products = []

                if lead.research_status != ResearchStatus.FAILED:
                    lead.research_status = ResearchStatus.PARTIAL

                lead.warnings.append(
                    "Search results are candidate evidence only. "
                    "Website, category, products and Amazon ownership "
                    "have not been verified."
                )
            else:
                lead.warnings.append(
                    "Synthetic demo data; not current brand research."
                )

            return lead

        except Exception as exc:
            return LeadRecord(
                brand=brand,
                input_source=source,
                category="unknown",
                research_status=ResearchStatus.FAILED,
                warnings=[
                    f"Brand research failed: "
                    f"{type(exc).__name__}: {exc}"
                ],
            )
