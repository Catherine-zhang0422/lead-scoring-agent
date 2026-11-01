from typing import Dict, Any
from agent.parser import LeadWebParser

class LeadResearcher:
    """Responsible for executing brand research and web content extraction."""

    def __init__(self):
        self.parser = LeadWebParser()

    def research_lead(self, lead_info: Dict[str, Any], raw_html: str = None) -> Dict[str, Any]:
        """
        Research lead: if real page HTML is provided, invoke parser to extract products and prices;
        otherwise, fallback to base data.
        """
        enriched_data = lead_info.copy()
        
        if raw_html:
            parsed_results = self.parser.parse_page(raw_html)
            enriched_data.update(parsed_results)
        else:
            if "representative_products" not in enriched_data:
                enriched_data["representative_products"] = []

        return enriched_data
