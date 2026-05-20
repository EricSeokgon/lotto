# Project Interview

## Round 1: Ownership and Purpose
Question: Who maintains this project and what is the primary goal going forward?
Answer: Active product being developed further — the CLI is v1.0 and new features (web dashboard, ML enhancements) are planned.

## Round 2: Constraints and Non-Goals
Question: What are the known constraints, technical debts, or things this project intentionally does NOT do?
Answer: No known critical constraints. File-based storage (CSV/JSON) is intentional — no database dependency. No winning number guarantee (statistical analysis only, disclaimer required).

## Round 3: Documentation Priority
Question: What is the most important aspect to capture accurately in the documentation?
Answer: Architecture and module boundaries — the 5 modules (collector, analyzer, recommender, simulator, models), their roles, interfaces, and dependency relationships should be documented with highest fidelity.
