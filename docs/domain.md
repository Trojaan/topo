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

`source classify-batch` is the bounded bulk decision for those open source
classification proposals. Exact selectors translate reviewed source groups to
canonical `domain.cashflow/classification/*` meaning. The effect-free preview
binds every selected proposal and target classification to one human
authorization; confirmation then publishes all assertions and source-proposal
decisions atomically in one generation. Overlapping, empty, stale, or already
classified selections fail as a whole.

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

Context inventory remains available for an otherwise empty package. It reports
requirements per affected analysis component rather than a global completeness
score, and keeps missing, conflicting, insufficiently current, and unallocated
context distinct. `workflow next` selects one deterministic typed follow-up action
and partial request template without executing or mutating anything.

Lifecycle administration remains an EngineCore mutation. Migration and restore
always publish a new validated generation; restore never moves `CURRENT` backward.
Retention is explicit and bounded, preserves requested recovery points, and records
removed generation identifiers without copying financial values. Privacy scrub is
the only package-wide rewrite: selected evidence and dependent proposal history are
removed from every retained generation, while surviving assertions lose the
removed provenance and become explicitly `unverifiable` rather than silently
remaining confirmed. Repeating a scrub after its targets are gone is effect-free.

`explain --ref` resolves proposals and decisions from validated canonical state
and resolves analysis components, analysis diagnostics, and rule outcomes from a
checksum-addressed derived index. The index is not financial context and never
advances `CURRENT`. An explanation is returned only while its stable reference,
payload, and used immutable generation remain verifiable; otherwise Topo returns
an explicit unknown or unverifiable-reference diagnostic and no invented explanation.
Presentation may summarize this structure, but may not add meaning or change its
stable English identifiers.

Domain modules own universal financial meaning. Jurisdiction modules overlay only
meaning that is genuinely jurisdiction-specific. Presentation language is a
separate concern, and machine identifiers stay stable English.

## Proactieve contextcyclus (context 0.2)

`workflow.next` inventariseert na iedere generatie de actuele context opnieuw en
herberekent de actieve effectvrije analyses. Het antwoord bevat altijd een
wijzigingsoverzicht, acht vaste contextsecties, analyseresultaten en hoogstens één
vervolgactie. De deterministische prioriteit is: migratie of integriteit,
batchautorisatie, feitenconflict, vereisten van het actieve doel, ontbrekende
basiscontext en ten slotte optionele verdieping.

De minimale basiscontext bestaat uit huishouden, rekeningen, terugkerende
cashflow, bezittingen, schulden, pensioenen, contracten/verzekeringen en doelen.
Ieder domein beheert een eigen `inventory_coverage`-bewering. Ontbrekende dekking
betekent onbekend. Alleen een bevestigde complete inventaris met een lege
`item_refs`-lijst betekent dat er voor dat domein geen items zijn; dit maakt
onbekende geldbedragen niet stilzwijgend nul.

Een antwoord via `workflow.respond` wordt één voorstelbatch met één bewijsrecord.
Nieuwe entiteiten en hun labels, typen, waarden, toerekeningen en dekking blijven
open voorstellen totdat `proposal.confirm-batch` een checksumgebonden preview en
expliciete menselijke autorisatie ontvangt. De batch wordt volledig gevalideerd
en in één generatie bevestigd of geheel niet gepubliceerd. Afwijzen gebeurt voor
de hele batch; correcties bewaren eerdere feiten en bewijs in de historie.
