from typing import List, Dict, Any

class LeadScorer:
    """Deterministic scoring engine to calculate lead scores based on extracted brand data."""

    def __init__(self, target_price_min: float = 15.0, target_price_max: float = 80.0):
        self.target_price_min = target_price_min
        self.target_price_max = target_price_max

    def score_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        score = 0.0
        breakdown = {}

        # Dimension 1: Country Match (+1.0)
        country = lead_data.get("country", "").upper()
        if country in ["UK", "GB", "UNITED KINGDOM"]:
            score += 1.0
            breakdown["country_match"] = 1.0
        else:
            breakdown["country_match"] = 0.0

        # Dimension 2: Retail Brand Match (+1.0)
        if lead_data.get("is_retail_brand", True):
            score += 1.0
            breakdown["retail_brand_match"] = 1.0

        # Dimension 3: Has Representative Products (+1.5)
        products = lead_data.get("representative_products", [])
        if products and len(products) > 0:
            score += 1.5
            breakdown["has_representative_products"] = 1.5
            
            # Dimension 4: Price Range Match (+1.5)
            prices = [p["price"] for p in products if "price" in p and isinstance(p["price"], (int, float))]
            if prices:
                avg_price = sum(prices) / len(prices)
                if self.target_price_min <= avg_price <= self.target_price_max:
                    score += 1.5
                    breakdown["price_range_match"] = 1.5
                else:
                    breakdown["price_range_match"] = 0.5
            else:
                breakdown["price_range_match"] = 0.0
        else:
            breakdown["has_representative_products"] = 0.0
            breakdown["price_range_match"] = 0.0

        return {
            "final_score": round(score, 2),
            "max_score": 5.0,
            "score_breakdown": breakdown,
            "representative_products": products
        }
