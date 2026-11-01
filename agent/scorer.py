import json
import os
import statistics
from typing import Any, Dict, List
from agent.models import LeadRecord, PriceTier, Grade, ScoreBreakdownItem


class ScoringEngine:
    def __init__(self, config_path: str = "config/scoring_config.json"):
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self._validate_config(config)
                return config
        return {
            "target_categories": ["Fashion", "Beauty", "Home & Living"],
            "rules": {
                "has_ecommerce_channel": 2,
                "category_match": 2,
                "price_tier": {
                    "premium": 2,
                    "mass_market": 1,
                    "luxury": 0,
                    "unknown": 0
                },
                "has_representative_products": 1
            },
            "grade_thresholds": {
                "A": 6,
                "B": 4,
                "C": 0
            }
        }

    def _validate_config(self, config: Dict[str, Any]) -> None:
        if "rules" not in config or "grade_thresholds" not in config:
            raise ValueError("Invalid configuration: missing 'rules' or 'grade_thresholds'.")
        if not isinstance(config["rules"].get("has_ecommerce_channel"), int):
            raise ValueError("Invalid configuration weight for has_ecommerce_channel.")

    def calculate_price_tier(self, products: List[Any]) -> tuple[PriceTier, str]:
        valid_prices = []
        for p in products:
            if p.price is not None and isinstance(p.price, (int, float)) and p.currency.upper() == "GBP" and p.price > 0:
                valid_prices.append(float(p.price))

        if not valid_prices:
            return PriceTier.UNKNOWN, "No verified GBP product prices available."

        sample_prices = valid_prices[:3]
        median_price = statistics.median(sample_prices)

        if median_price < 30.0:
            tier = PriceTier.MASS_MARKET
        elif 30.0 <= median_price <= 150.0:
            tier = PriceTier.PREMIUM
        else:
            tier = PriceTier.LUXURY

        basis = f"Median price £{median_price:.2f} across {len(sample_prices)} verified GBP product(s)."
        return tier, basis

    def score_lead(self, lead: LeadRecord) -> LeadRecord:
        rules = self.config["rules"]
        target_categories = [c.lower() for c in self.config["target_categories"]]
        thresholds = self.config["grade_thresholds"]

        score_breakdown: List[ScoreBreakdownItem] = []
        total_score = 0

        ecommerce_points = rules.get("has_ecommerce_channel", 2)
        has_ecom = lead.has_ecommerce_channel or (lead.amazon_relationship in ("verified_official", "third_party") and lead.amazon_url is not None)
        ecom_ev_ids = [e.id for e in lead.evidence if "ecommerce" in e.summary.lower() or "shop" in e.summary.lower() or "store" in e.summary.lower()]
        if not ecom_ev_ids and lead.evidence:
            ecom_ev_ids = [lead.evidence[0].id]

        if has_ecom:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="has_ecommerce_channel",
                observed_value=True,
                points=ecommerce_points,
                reason="Verified online purchase entry or official Amazon UK presence.",
                evidence_ids=ecom_ev_ids
            ))
            total_score += ecommerce_points
        else:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="has_ecommerce_channel",
                observed_value=False,
                points=0,
                reason="No verified online purchase entry or official store found.",
                evidence_ids=[]
            ))

        cat_points = rules.get("category_match", 2)
        cat_match = lead.category.lower() in target_categories
        cat_ev_ids = [e.id for e in lead.evidence if lead.category.lower() in e.summary.lower()]
        if cat_match:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="category_match",
                observed_value=lead.category,
                points=cat_points,
                reason=f"Brand category '{lead.category}' matches target retail sectors.",
                evidence_ids=cat_ev_ids
            ))
            total_score += cat_points
        else:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="category_match",
                observed_value=lead.category,
                points=0,
                reason=f"Category '{lead.category}' is outside primary target sectors.",
                evidence_ids=[]
            ))

        tier, basis = self.calculate_price_tier(lead.representative_products)
        lead.price_tier = tier
        lead.price_basis = basis

        tier_rules = rules.get("price_tier", {})
        tier_points = tier_rules.get(tier.value, 0)
        tier_ev_ids = [p.evidence_id for p in lead.representative_products if p.evidence_id]

        score_breakdown.append(ScoreBreakdownItem(
            criterion="price_tier",
            observed_value=tier.value,
            points=tier_points,
            reason=basis,
            evidence_ids=tier_ev_ids
        ))
        total_score += tier_points

        prod_points = rules.get("has_representative_products", 1)
        has_prods = len(lead.representative_products) > 0
        if has_prods:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="has_representative_products",
                observed_value=len(lead.representative_products),
                points=prod_points,
                reason=f"Identified {len(lead.representative_products)} verified representative product(s).",
                evidence_ids=tier_ev_ids
            ))
            total_score += prod_points
        else:
            score_breakdown.append(ScoreBreakdownItem(
                criterion="has_representative_products",
                observed_value=0,
                points=0,
                reason="Insufficient representative products verified with GBP pricing.",
                evidence_ids=[]
            ))

        lead.score = total_score

        if total_score >= thresholds.get("A", 6):
            lead.grade = Grade.A
        elif total_score >= thresholds.get("B", 4):
            lead.grade = Grade.B
        else:
            lead.grade = Grade.C

        scored_criteria = 4
        criteria_with_evidence = sum(1 for item in score_breakdown if len(item.evidence_ids) > 0)
        lead.evidence_coverage = round(criteria_with_evidence / scored_criteria, 2)
        lead.score_breakdown = score_breakdown

        if lead.research_status == ResearchStatus.FAILED:
            lead.priority_note = f"Research failed for {lead.brand}; manual review required."
            lead.recommended_next_step = "Check website availability or verify directory entry manually."
        else:
            lead.priority_note = f"Score {total_score} (Grade {lead.grade}) with {int(lead.evidence_coverage * 100)}% evidence coverage."
            lead.recommended_next_step = "Review representative product pricing and initiate tailored BD outreach."

        return lead
