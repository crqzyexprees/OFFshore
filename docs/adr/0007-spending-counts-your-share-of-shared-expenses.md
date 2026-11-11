# 7. Spending counts your Share of a Shared Expense

Date: 2026-11-10
Status: Accepted

## Context

SplitLens (the Next.js app this one replaces) tracked Splitwise expenses beside card
spending but never folded them into it: a $90 dinner paid by card and split three ways
counted as $90 of Dining, and a dinner a friend paid counted as nothing. Its Splitwise
importer also read each member's column as their share, but a Splitwise export column is
the member's *net* (what they paid minus their share), so the payer's share came out as
what the others owed them ($60, not $30). Importing a file twice duplicated everything.

## Decision

Spending counts the user's Share of a Shared Expense, not what was charged or paid:

- **Someone else paid**: the user's Share is Spending in the expense's Category, on its
  date, and the user owes the payer that Share.
- **The user paid, and the expense is linked to the Purchase that paid for it**: that
  Purchase counts as the user's Share instead of its full amount, in the Purchase's
  Category. The other Shares are owed to the user.
- **The user paid but it isn't linked yet**: it isn't Spending until it is linked on
  Reconcile, so the card Purchase is never counted twice. If it was paid outside the
  tracked Accounts (cash, say), the user marks it so, and the Share counts on its own.
- **Settlements** (Splitwise "Payment" rows, "Mark settled") change Balances, never Spending.

One SQL view, `spending_items`, holds these rules; Spending and Budgets both read it.

Splitwise group exports are read as nets. With one payer, a non-payer's Share is minus
their net and the payer's Share is the cost minus their net. Rows with several payers
that include the user can't be split that way and are reported, not guessed. Each row is
keyed by its contents, so importing the same file again adds only new rows.

A link to a Transaction survives the Statement being imported again: links are carried
over by the same match as Overrides (docs/adr/0005).

## Consequences

- Spending, the Dashboard and Budgets show what the user actually spent.
- Until a card-paid expense is linked, that Purchase counts in full; Reconcile lists the
  unlinked ones with suggested matches.
- Balances per Person are derived, never stored, so they can't drift from the expenses.
