import json
from pathlib import Path
from statistics import median

from agent.models import (
    Grade,
    LeadRecord,
    PriceTier,
    ScoreBreakdownItem,
)


class ScoringEngine:
    """Calculate lead scores using configurable, deterministic rules."""

    def __init__(self, config_path="config/scoring_config.json"):
        path = Path(config_path)

        if not path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            path = project_root / path

        with path.open("r", encoding="utf-8") as file:
            self.config = json.load(file)

        self.rules = self.config["rules"]
        self.thresholds = self.config["grade_thresholds"]
        self.target_categories = {
            category.strip().casefold()
            for category in self.config["target_categories"]
        }

        weights = [
            self.rules["has_ecommerce_channel"],
            self.rules["category_match"],
            self.rules["has_representative_products"],
            *self.rules["price_tier"].values(),
        ]

        if any(
            type(weight) is not int or weight < 0
            for weight in weights
        ):
            raise ValueError("Scoring weights must be non-negative integers.")

        thresholds = [
            self.thresholds[key] for key in ("A", "B", "C")
        ]

        if any(type(value) is not int for value in thresholds):
            raise ValueError("Grade thresholds must be integers.")

        if not (
            self.thresholds["A"] > self.thresholds["B"]
            > self.thresholds["C"] == 0
        ):
            raise ValueError("Grade thresholds must satisfy A > B > C = 0.")

    def score_lead(self, lead: LeadRecord) -> LeadRecord:
        # Evidence IDs must refer to evidence actually stored on this lead.
        evidence_by_id = {
            item.id: item
            for item in lead.evidence
            if item.source_url.strip() and item.summary.strip()
        }
        evidence_ids = list(evidence_by_id)

        # Only products with a matching evidence record are eligible.
        products = [
            product
            for product in lead.representative_products
            if product.name.strip()
            and product.url
            and product.evidence_id in evidence_by_id
        ][:3]

        priced_products = [
            product
            for product in products
            if product.currency.upper() == "GBP"
            and product.price is not None
            and product.price > 0
        ]

        if priced_products:
            median_price = median(
                product.price for product in priced_products
            )

            if median_price < 30:
                lead.price_tier = PriceTier.MASS_MARKET
            elif median_price <= 150:
                lead.price_tier = PriceTier.PREMIUM
            else:
                lead.price_tier = PriceTier.LUXURY

            lead.price_basis = (
                f"Median GBP price: £{median_price:.2f}; "
                f"sample size: {len(priced_products)}."
            )
        else:
            lead.price_tier = PriceTier.UNKNOWN
            lead.price_basis = "Insufficient verified GBP product prices."

        breakdown = []

        def add_item(criterion, observed_value, points, reason, ids):
            breakdown.append(
                ScoreBreakdownItem(
                    criterion=criterion,
                    observed_value=observed_value,
                    points=points,
                    reason=reason,
                    evidence_ids=ids,
                )
            )

        # A positive signal needs supporting evidence to receive points.
        has_ecommerce = (
            lead.has_ecommerce_channel is True
            and bool(evidence_ids)
        )
        add_item(
            "has_ecommerce_channel",
            lead.has_ecommerce_channel,
            self.rules["has_ecommerce_channel"] if has_ecommerce else 0,
            (
                "Reported e-commerce channel with supporting lead evidence."
                if has_ecommerce
                else "No supported positive e-commerce signal."
            ),
            evidence_ids if has_ecommerce else [],
        )

        category_known = (
            bool(lead.category.strip())
            and lead.category.strip().casefold() != "unknown"
            and bool(evidence_ids)
        )
        category_match = (
            category_known
            and lead.category.strip().casefold()
            in self.target_categories
        )
        add_item(
            "category_match",
            lead.category,
            self.rules["category_match"] if category_match else 0,
            (
                "Category matches the configured target categories."
                if category_match
                else "Category is outside the target set or unsupported."
            ),
            evidence_ids if category_known else [],
        )

        price_evidence_ids = sorted({
            product.evidence_id
            for product in priced_products
        })
        add_item(
            "price_tier",
            lead.price_tier.value,
            self.rules["price_tier"].get(lead.price_tier.value, 0),
            lead.price_basis,
            price_evidence_ids,
        )

        product_evidence_ids = sorted({
            product.evidence_id for product in products
        })
        add_item(
            "has_representative_products",
            bool(products),
            self.rules["has_representative_products"] if products else 0,
            (
                f"{len(products)} representative product(s) with evidence."
                if products
                else "No representative products with matching evidence."
            ),
            product_evidence_ids,
        )

        lead.score_breakdown = breakdown
        lead.score = sum(item.points for item in breakdown)

        if lead.score >= self.thresholds["A"]:
            lead.grade = Grade.A
        elif lead.score >= self.thresholds["B"]:
            lead.grade = Grade.B
        else:
            lead.grade = Grade.C

        lead.evidence_coverage = round(
            sum(bool(item.evidence_ids) for item in breakdown)
            / len(breakdown),
            2,
        )

        lead.priority_note = (
            f"Grade {lead.grade.value}, score {lead.score}; "
            f"evidence coverage {lead.evidence_coverage:.0%}."
        )
        lead.recommended_next_step = (
            "Review source evidence and resolve missing or uncertain facts."
        )

        return lead
