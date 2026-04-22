from typing import Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, JSON, Column
import json


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    motion_sku: str = Field(index=True, unique=True)
    mfr_name: str
    mfr_part_number: str
    description: str
    product_type: str = ""
    bore_diameter: str = ""
    outside_diameter: str = ""
    overall_width: str = ""
    closure_type: str = ""
    bearing_material: str = ""
    series: str = ""
    max_rpm: str = ""
    weight: str = ""
    radial_dynamic_load: str = ""
    radial_static_load: str = ""
    internal_clearance: str = ""
    precision_rating: str = ""
    upc: str = ""
    source_url: str = ""
    image_status: str = Field(default="no_image")  # no_image | pending | matched | approved | rejected
    approved_image_url: str = ""
    approved_image_score: float = 0.0
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class ImageCandidate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    image_url: str
    thumbnail_url: str = ""
    source_domain: str = ""
    source_query: str = ""
    title: str = ""
    # Scores
    url_relevance_score: float = 0.0
    title_relevance_score: float = 0.0
    domain_trust_score: float = 0.0
    composite_score: float = 0.0
    confidence_tier: str = ""  # high | medium | low
    # Status
    status: str = "candidate"  # candidate | approved | rejected
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
