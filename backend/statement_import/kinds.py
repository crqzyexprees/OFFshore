"""Rules deciding a Transaction's kind (GLOSSARY.md: Transaction).

The model never decides kinds: it has no bank-account training data. These
rules give the default; the user corrects them with Overrides or Merchant rules.
"""

import re
from dataclasses import dataclass

_WITHDRAWAL = re.compile(r"\bATM\b(?!.*\bFEE)", re.I)
_PEER = re.compile(r"\bZELLE\b|\bVENMO\b|\bCASH ?APP\b|\bCHE?C?K\s*#?\s*\d+", re.I)
_CARD_PAYOFF_FROM_BANK = re.compile(
    r"CRD AUTOPAY|CREDIT CARD|CARD PAYMENT|CRCARDPMT|E-?PAYMENT|AUTO ?PA?YMT|AUTOPAY", re.I
)
_PAYMENT_TO_CARD = re.compile(r"PAYMENT|AUTOPAY|AUTO-PMT|THANK YOU", re.I)
_OWN_TRANSFER = re.compile(r"\bTRANSFER (?:TO|FROM)\b|\bXFER\b", re.I)
_REWARD = re.compile(r"REWARD|CASH ?BACK|REDEMPTION|STATEMENT CREDIT", re.I)
_INCOME = re.compile(
    r"PAYROLL|DIRECT DEP|DIR DEP|SALARY|INTEREST (?:PAYMENT|PAID|EARNED)|INTEREST$"
    r"|IRS TREAS|TAX REF|SSA TREAS",
    re.I,
)
_BANK_REFUND = re.compile(r"REFUND|RETURN", re.I)


@dataclass(frozen=True)
class OtherAccounts:
    """Which other Accounts the user tracks; a Transfer is Internal only when
    the Account on the other side is tracked."""

    bank: bool
    credit_card: bool

    @property
    def any(self) -> bool:
        return self.bank or self.credit_card


def decide_kind(description: str, direction: str, account_kind: str, others: OtherAccounts) -> str:
    def transfer(other_side_tracked: bool) -> str:
        return "internal_transfer" if other_side_tracked else "peer_transfer"

    if direction == "out" and _WITHDRAWAL.search(description):
        return "withdrawal"
    if _PEER.search(description):
        return "peer_transfer"

    if account_kind == "credit_card":
        if direction == "out":
            return "purchase"
        if _REWARD.search(description):
            return "reward"
        # Paying off a card always comes from one of the user's own Accounts.
        if _PAYMENT_TO_CARD.search(description):
            return "internal_transfer"
        return "refund"

    # Bank Account.
    if _OWN_TRANSFER.search(description):
        return transfer(others.any)
    if direction == "out":
        if _CARD_PAYOFF_FROM_BANK.search(description):
            return "internal_transfer"
        return "purchase"
    if _INCOME.search(description):
        return "income"
    if _BANK_REFUND.search(description):
        return "refund"
    return "income"
