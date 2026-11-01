import os
import pytest
from agent.parser import parse_input_file, is_safe_url
from agent.models import LeadRecord, Product, PriceTier, Grade
from agent.scorer import ScoringEngine
from agent.searcher import FixtureSearchAdapter
from agent.researcher import BrandResearcher
from agent.providers import DemoLLMProvider


def test_url_safety_check():
    assert is_safe_url("https://example.com/exhibitors") is True
    assert is_safe_url("http://localhost:8080/admin") is False
    assert is_safe_url("http://127.0.0.1/secret") is False
    assert is_safe_url("http://169.254.169.254/latest/meta-data") is False
    assert is_safe_url("ftp://example.com") is False


def test_csv_parser(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "test_brands.csv"
    p.write_text("brand,category,website\n  Aura London  , Fashion , https://aura.example.com \n", encoding="utf-8")

    records, warnings = parse_input_file(str(p))
    assert len(records) == 1
    assert records[0]["brand"] == "Aura London"
    assert records[0]["category"] == "Fashion"
    assert records[0]["website"] == "https://aura.example.com"


def test_scoring_engine_and_price_tier():
    engine = ScoringEngine()

    lead_mass = LeadRecord(
        brand="Test Brand Mass",
        input_source="test",
        has_ecommerce_channel=True,
        category="Fashion",
        representative_products=[
            Product(name="P1", price=15.00, currency="GBP", evidence_id="ev_1"),
            Product(name="P2", price=25.00, currency="GBP", evidence_id="ev_2")
        ]
    )
    scored_mass = engine.score_lead(lead_mass)
    assert scored_mass.price_tier == PriceTier.MASS_MARKET
    assert scored_mass.score >= 4

    lead_lux = LeadRecord(
        brand="Test Brand Luxury",
        input_source="test",
        has_ecommerce_channel=False,
        category="Unknown Sector",
        representative_products=[
            Product(name="P3", price=200.00, currency="GBP", evidence_id="ev_3")
        ]
    )
    scored_lux = engine.score_lead(lead_lux)
    assert scored_lux.price_tier == PriceTier.LUXURY
    assert scored_lux.score == 0


def test_demo_research_and_pipeline():
    searcher = FixtureSearchAdapter()
    llm = DemoLLMProvider()
    researcher = BrandResearcher(searcher, llm)
    engine = ScoringEngine()

    brand_info = {"brand": "Aura London", "category": "Fashion", "source_url": "sample_csv"}
    lead = researcher.research_brand(brand_info)
    scored = engine.score_lead(lead)

    assert scored.brand == "Aura London"
    assert scored.grade == Grade.A
    assert scored.evidence_coverage > 0.0
