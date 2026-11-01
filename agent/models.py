from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WebsiteStatus(str, Enum):
    ACTIVE = "active"
    ERROR = "error"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class AmazonPresence(str, Enum):
    OFFICIAL_STORE = "official_store"
    PRODUCT_LISTING = "product_listing"
    NONE = "none"
    UNKNOWN = "unknown"


class AmazonRelationship(str, Enum):
    VERIFIED_OFFICIAL = "verified_official"
    THIRD_PARTY = "third_party"
    UNCERTAIN = "uncertain"
    NONE = "none"


class PriceTier(str, Enum):
    MASS_MARKET = "mass_market"  # < £30
    PREMIUM = "premium"  # £30 - £150 inclusive
    LUXURY = "luxury"  # > £150
    UNKNOWN = "unknown"


class ResearchStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class Grade(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class Product(BaseModel):
    name: str
    url: Optional[str] = None
    price: Optional[float] = None
    currency: str = "GBP"
    evidence_id: Optional[str] = None


class EvidenceItem(BaseModel):
    id: str
    source_url: str
    summary: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ScoreBreakdownItem(BaseModel):
    criterion: str
    observed_value: Any
    points: int
    reason: str
    evidence_ids: List[str] = Field(default_factory=list)


class LeadRecord(BaseModel):
    brand: str
    input_source: str
    website: Optional[str] = None
    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN
    has_ecommerce_channel: bool = False
    amazon_url: Optional[str] = None
    amazon_presence: AmazonPresence = AmazonPresence.UNKNOWN
    amazon_relationship: AmazonRelationship = AmazonRelationship.UNKNOWN
    category: str = "unknown"
    representative_products: List[Product] = Field(default_factory=list)
    price_tier: PriceTier = PriceTier.UNKNOWN
    price_basis: str = "Insufficient or unverified GBP pricing data"
    evidence: List[EvidenceItem] = Field(default_factory=list)
    research_status: ResearchStatus = ResearchStatus.PARTIAL
    warnings: List[str] = Field(default_factory=list)
    score: int = 0
    grade: Grade = Grade.C
    score_breakdown: List[ScoreBreakdownItem] = Field(default_factory=list)
    evidence_coverage: float = 0.0
    priority_note: str = ""
    recommended_next_step: str = ""
    researched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
