# Domain and safety boundary

Topo maps a person's or household's financial context. It preserves facts,
relationships, time, evidence, assumptions, and derived results so every outcome
can explain its inputs. The full Dutch ubiquitous language is in `CONTEXT.md`.

The key boundary is between observed or user-confirmed context and interpreted
meaning. An agent, importer, or rule can submit a structured proposal; it cannot
write a confirmed financial fact directly. Confirmation requires an explicit
human authorization bound to the preview being approved.

An explicitly identified source adapter is the narrow exception for literal
observations. `source import` first returns an effect-free preview, and publication
requires human authorization bound to that preview. It may then persist a
transaction's source account, booking date, money, description, and stable source
identity as observed evidence. A source correction creates linked successor
evidence and assertions; it never replaces the earlier records. Source
classifications and explanations remain open proposals until a human confirms
their financial meaning.

`analyze run` with `analysis.realized_monthly_cashflow` reads one explicit,
half-open calendar month. Confirmed paired transfers are excluded from income and
expense, while every included posting remains in net movement. Unclassified
postings make only the category breakdown provisional. Core totals are complete
only when each included account has a confirmed full household allocation and
transaction coverage for the whole month.

`discover run` reads the current literal transaction observations without making
a generation. The cashflow recognition module compares direction, normalized
description, currency, interval, and amount. It recognizes weekly, four-weekly,
monthly, quarterly, and annual candidates; returns their evidence, expected
period, amount or range, deviations, rule version, and module-specific score; and
returns `INSUFFICIENT_PATTERN_HISTORY` instead of inventing a pattern when the
minimum history is absent. A candidate only enters canonical history when its
submit-ready proposal is explicitly passed to `proposal submit`.

Declarative rule packages are complete, versioned module artifacts. `rule
validate` accepts only the registered recognition, validation, completeness, and
question-priority capabilities; unknown predicates, cross-view fields, custom
YAML tags, free expressions, and mismatched outcomes fail closed. `rule preview`
is effect-free and returns an explanation trace for every rule, predicate,
input-view, and condition. `rule activate` requires a human authorization bound to
that preview and the current manifest generation; successful activation replaces
the module's full package atomically without granting rules code, storage, query,
or context-mutation access.

`analyze run` with `analysis.normalized_monthly_cashflow` reads confirmed recurring
cashflows for one explicit scope at `as_of_date`. It converts weekly, four-weekly,
monthly, quarterly, and annual amounts to a month without mutating the context.
Ranges remain ranges; Topo never invents their midpoint, and only a confirmed
`typical_money` may contribute to an expected total.

`analyze run` with `analysis.net_worth` reads current confirmed account balances,
asset values, debt balances, and pension values by `economic_interest_ref`.
Directly scoped values or values with a complete explicit allocation contribute
once. Restricted pension remains a separate component. Original-currency
subtotals survive missing exchange rates; only dependent totals become
unavailable. Missing values stay visible and conflicts remain local.

`analyze run` with `analysis.scenario_comparison` compares one explicit scenario
with the baseline on a future `as_of_date`. Its assumptions are limited to dated
recurring-cashflow changes, one-off cashflows, and value overrides with a target,
currency, and reason. The result keeps baseline, scenario, and delta separate and
marks the comparison as projected knowledge. A cashflow improvement never becomes
wealth automatically; without an explicit destination Topo reports
`CASHFLOW_DESTINATION_NOT_MODELED`.

Topo produces traceable facts, calculations, gaps, uncertainties, and scenarios.
It does not produce regulated financial advice or silently fill missing values.
Material, complex, or potentially regulated decisions require qualified human
review outside the engine.

Domain modules own universal financial meaning. Jurisdiction modules overlay only
meaning that is genuinely jurisdiction-specific. Presentation language is a
separate concern, and machine identifiers stay stable English.
