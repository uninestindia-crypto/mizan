"""Strategy Lab: honest backtests of simple retail strategies on real NSE daily data.

Rules the lab never breaks:

* Real cached bars only; a decision made at a session's close fills at the next session's open.
* Every fill pays the NSE statutory charges in force on its trade date, plus the user's broker
  charges and slippage. Trades are refused on dates the dated rule catalog cannot price.
* Every result is compared with NIFTYBEES bought and held over the same sessions with the same
  costs, and judged by a multiplicity-adjusted probability, never by the raw return alone.
"""

from __future__ import annotations

from quant_system.lab.costs import COSTS_COVERED_FROM, BrokerCharges, RetailCostModel
from quant_system.lab.runner import LabError, LabRequest, run_lab
from quant_system.lab.templates import TEMPLATES, get_template

__all__ = [
    "COSTS_COVERED_FROM",
    "TEMPLATES",
    "BrokerCharges",
    "LabError",
    "LabRequest",
    "RetailCostModel",
    "get_template",
    "run_lab",
]
