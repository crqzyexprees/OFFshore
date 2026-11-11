# Personal Spending

Tracks one person's spending across their credit cards and bank accounts, built from the bank Statements they import, so they can see their Spending by Category.

## Language

### Sources

**Account**:
A credit card or bank account whose Statements the user imports. A debit card is not an Account; its Transactions belong to the bank Account it draws from.
_Avoid_: Card (a credit card is one kind of Account)

**Statement**:
One document from a bank listing an Account's Transactions for a billing period, as printed on the Statement. A Statement is identified by its Account and billing period; importing the same period again replaces it.
_Avoid_: Bill, PDF, file

### Money movement

**Transaction**:
One line on a Statement: the date it happened (not the date it posted), a description, and an amount of money leaving or entering an Account. Every Transaction is exactly one of: Purchase, Refund, Transfer, Income, Withdrawal, Reward.
_Avoid_: Charge, entry

**Purchase**:
Money spent with a merchant, including any cash taken at checkout; it counts as Spending in its Category.
_Avoid_: Debit, charge, expense

**Refund**:
Money returned to an Account that reverses an earlier Purchase; it reduces Spending in its Category.
_Avoid_: Credit, return

**Transfer**:
Money moving between the user and another person, or between two of the user's own Accounts. Not Spending. Every Transfer is either an Internal Transfer or a Peer Transfer.
_Avoid_: Payment, card payment, Zelle

**Internal Transfer**:
A Transfer between two Accounts the user tracks, such as paying off a credit card from a bank Account. Card payments are always Internal Transfers, even when the other Account isn't tracked.
_Avoid_: Card payment, self-transfer

**Peer Transfer**:
A Transfer to or from another person, or to an Account the user doesn't track.
_Avoid_: P2P, Zelle, Venmo

**Income**:
Money paid to the user by an employer, bank, or government, such as salary, interest, or a tax refund. Not Spending.
_Avoid_: Deposit, credit

**Reward**:
Cash back or another reward the card issuer credits to a credit card Account. Not Spending and not Income.
_Avoid_: Cash back, rewards redemption, statement credit

**Withdrawal**:
Cash taken out of an Account at an ATM. Not Spending; shown as its own total.
_Avoid_: ATM/Cash, cash advance

**Spending**:
Purchases minus Refunds, per Category, grouped by the calendar month of each Transaction's date. It can be negative when Refunds exceed Purchases.
_Avoid_: Expenses, outflow, total

### Categorisation

**Category**:
The spending class a Purchase or Refund belongs to, such as Groceries or Dining. Categories come from one fixed, curated list.
_Avoid_: Tag, label, type

**Override**:
A kind or Category the user assigns to one Transaction by hand. It affects that Transaction only and always wins over a Merchant rule or prediction.
_Avoid_: Correction, manual category, edit

**Merchant rule**:
A user-defined rule that assigns a kind, a Category, or both to every Transaction whose description matches it, past and future, except Overridden ones.
_Avoid_: Auto-categorisation, alias
