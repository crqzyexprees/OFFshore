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

**Export**:
A CSV, OFX or QFX file a bank offers for download in place of a PDF Statement. Importing one creates a Statement like a PDF does; an OFX/QFX file names its Account and billing period, but a CSV usually names neither, so the user gives them.
_Avoid_: Download, CSV statement

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
Purchases minus Refunds, per Category, grouped by the calendar month of each Transaction's date, plus the user's Share of Shared Expenses others paid; a Linked Purchase counts as the user's Share. It can be negative when Refunds exceed Purchases.
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

### Sharing

**Person**:
Someone the user splits costs with. People are kept on this device only; they never sign in.
_Avoid_: Contact, friend, user

**Group**:
A named set of People the user often splits with, such as housemates. A Splitwise group imports as one.
_Avoid_: Team, circle

**Shared Expense**:
One cost split between the user and one or more People, paid by the user or by one Person. It records the total, who paid, and each Share.
_Avoid_: Split, bill, Splitwise expense

**Share**:
The part of a Shared Expense that one person is responsible for. The user's Share is what counts as Spending (docs/adr/0007).
_Avoid_: Portion, cut, amount owed

**Link**:
The connection between a Shared Expense the user paid and the Purchase that paid for it. Once linked, that Purchase counts as the user's Share.
_Avoid_: Match, reconciliation

**Settlement**:
Money that pays off a Balance between the user and a Person. It changes the Balance, never Spending.
_Avoid_: Payment, settle-up, repayment

**Balance**:
What one Person owes the user (positive) or the user owes them (negative), from all Shared Expenses and Settlements between them.
_Avoid_: Debt, IOU, net

### Planning

**Budget**:
The most a user means to spend in a Category each month, compared with that month's Spending. A Budget applies from the month it is set until it is changed or removed; changing it never changes earlier months.
_Avoid_: Limit, plan, target
