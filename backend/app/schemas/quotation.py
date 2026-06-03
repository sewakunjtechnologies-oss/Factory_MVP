from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class QuotationLineRead(BaseModel):
    description: str
    quantity_pcs: int
    unit_price: Optional[Decimal]
    amount: Optional[Decimal]


class POQuotationRead(BaseModel):
    po_number: str
    buyer_name: Optional[str]
    product: str
    product_category: str
    design_code: Optional[str]
    quantity_pcs: int
    unit_price: Optional[Decimal]
    subtotal: Optional[Decimal]
    tax_rate_percent: Optional[Decimal]
    tax_amount: Optional[Decimal]
    total_amount: Optional[Decimal]
    dispatch_date: date
    missing_fields: List[str]
    terms: List[str]
    lines: List[QuotationLineRead]
