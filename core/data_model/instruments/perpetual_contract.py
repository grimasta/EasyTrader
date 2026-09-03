from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from core.data_model.instruments.abstract_instrument import AbstractInstrument


@dataclass
class PerpetualContract(AbstractInstrument):
    """
    Canonical data model for a perpetual futures contract.

    Extends AbstractInstrument with fields specific to leveraged perpetual
    contracts: leverage bounds, margin model, fees, funding, and position
    size limits. Spot, equity, and option instruments use their own subclasses.

    Construction belongs in the venue layer. The parser for each venue
    produces a PerpetualContract from raw API response data and is
    responsible for normalising all field names and casting all values
    to the types declared here.
    """

    # --- Settlement ---
    settlement_asset: str
    """Asset in which P&L is settled. 'USDT' for linear, base asset for inverse."""

    contract_size: Decimal
    """Units of base asset per contract. 1.0 for most linear perpetuals."""

    # --- Leverage ---
    max_leverage: int
    """Maximum leverage allowed. May be lower during low-liquidity periods."""

    min_leverage: int
    """Minimum leverage allowed. Typically 1; explicitly provided by some venues."""

    # --- Order size limits ---
    min_notional: Optional[Decimal]
    """Minimum order value in the quote asset (e.g. 5 USDT). None if not enforced."""

    max_qty: Optional[Decimal]
    """Maximum limit order quantity in the base asset. None if not enforced."""

    max_market_qty: Optional[Decimal]
    """Maximum market order quantity in the base asset. None if not enforced."""

    # --- Fees ---
    maker_fee_rate: Optional[Decimal]
    """Maker rebate or fee as a decimal, e.g. 0.0002 for 0.02%. None if not in spec."""

    taker_fee_rate: Optional[Decimal]
    """Taker fee as a decimal, e.g. 0.0006 for 0.06%. None if not in spec."""

    # --- Funding ---
    funding_interval_hours: Optional[int]
    """Hours between funding payments. Typically 8. None if not in spec."""

    # --- Risk parameters ---
    maintenance_margin_pct: Optional[Decimal]
    """Maintenance margin as a percentage, e.g. 2.5 for 2.5%. None if not in spec."""

    liquidation_fee_rate: Optional[Decimal]
    """Fee charged on liquidation as a decimal. None if not in spec."""

    def instrument_category(self) -> str:
        return "perpetual"