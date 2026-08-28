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

`discover run` reads the current literal transaction observations without making
a generation. The cashflow recognition module compares direction, normalized
description, currency, interval, and amount. It recognizes weekly, four-weekly,
monthly, quarterly, and annual candidates; returns their evidence, expected
period, amount or range, deviations, rule version, and module-specific score; and
returns `INSUFFICIENT_PATTERN_HISTORY` instead of inventing a pattern when the
minimum history is absent. A candidate only enters canonical history when its
submit-ready proposal is explicitly passed to `proposal submit`.

Topo produces traceable facts, calculations, gaps, uncertainties, and scenarios.
It does not produce regulated financial advice or silently fill missing values.
Material, complex, or potentially regulated decisions require qualified human
review outside the engine.

Domain modules own universal financial meaning. Jurisdiction modules overlay only
meaning that is genuinely jurisdiction-specific. Presentation language is a
separate concern, and machine identifiers stay stable English.
