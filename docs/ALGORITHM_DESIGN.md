# AgroNexus AI Algorithm Design

## Purpose

This document specifies the algorithms that form the AgroNexus AI research contribution. Specialist models such as crop recommendation, disease classification, yield prediction, fertilizer suitability, irrigation estimation, and risk prediction produce evidence. They do not make the final agricultural decision. The decision layer combines that evidence, records what happened after a recommendation, and changes future decisions using the recorded outcome.

The first implementation target is a software-only decision-support system. AgroNexus recommends and explains actions; it does not automatically operate farm equipment.

## Algorithm Set

| ID | Algorithm | Purpose |
| --- | --- | --- |
| A0 | Evidence Normalization | Convert outputs from farmer input, datasets, APIs, and ML models into a common evidence record. |
| A1 | ERP and Evidence Sufficiency | Decide whether the available evidence is adequate for a decision and identify the highest-priority missing evidence. |
| A2 | Decision State Construction | Build the current agricultural context from decision-ready evidence. |
| A3 | ADIE-1 | Generate feasible actions, score them under the current context, and choose a recommendation. |
| A4 | ACER | Record the action, execution context, expected outcome, observed outcome, and deviation. |
| A5 | CNDA | Find contextual dimensions statistically associated with the deviation for similar prior cases. |
| A6 | Joint Adaptive Update | Update both action-context effectiveness and ERP weights from an ACER. |

## Shared Data Contracts

### Evidence item

Each input, API response, or model output is stored as an `EvidenceItem`.

```text
evidence_id, decision_id, attribute, value, unit, source_type,
quality_q, reliability_r, captured_at, latitude, longitude,
valid_until, model_version, provenance, confidence
```

All quality-like values use the interval `[0, 1]`.

- `quality_q`: completeness, validation status, and measurement quality.
- `reliability_r`: trust assigned to the source or model.
- `confidence`: confidence reported by a model, if applicable.
- `provenance`: source and version needed to audit the recommendation.

### Decision state

```text
decision_type, farm_id, field_id, crop, crop_stage, location,
soil, weather, disease_or_risk, resources, budget, farmer_constraints,
evidence_scores, evidence_provenance, timestamp
```

### Evidence Requirement Profile

An ERP is stored per decision type, such as `crop_selection`, `disease_intervention`, `fertilizer`, or `irrigation`.

```text
decision_type, attribute, weight_w, required, minimum_score,
temporal_validity_days_tau, spatial_validity_km_rho,
inclusion_floor, acquisition_priority, version
```

### Action Context Effect Record

```text
acer_id, decision_id, action_id, action_version, context_vector,
expected_outcome, observed_outcome, deviation,
outcome_measure, outcome_confidence, feedback_completeness,
associated_factors, association_confidence, created_at
```

`context_vector` contains normalized fields such as crop, crop stage, disease severity, rainfall forecast, temperature, soil values, location, season, resource availability, and budget class.

## A0 Evidence Normalization

### Objective

Put evidence from different sources into one comparable representation without discarding its source, freshness, or uncertainty.

### Evidence score

For an evidence attribute `i`, calculate:

```text
e_i = a_i * q_i * r_i * t_i * p_i * c_i
```

Where:

- `a_i` is availability: `1` when present and `0` when absent.
- `q_i` is quality.
- `r_i` is source reliability.
- `t_i` is temporal validity.
- `p_i` is spatial validity.
- `c_i` is model confidence; use `1` for non-model evidence when no confidence applies.

Temporal validity decays linearly:

```text
t_i = max(0, 1 - age_i / tau_i)
```

Spatial validity decays linearly when a location is relevant:

```text
p_i = max(0, 1 - distance_i / rho_i)
```

`tau_i` and `rho_i` come from the ERP. If an attribute has no spatial requirement, `p_i = 1`.

### Implementation

Create a pure backend service that validates units, converts values to canonical units, computes `e_i`, and returns normalized evidence plus provenance. Unit tests will cover missing values, expired evidence, distant evidence, and conflicting values.

## A1 ERP and Evidence Sufficiency

### Objective

Determine whether there is enough trustworthy and current information to make a decision. A low score does not force a recommendation; it returns an evidence-acquisition plan.

### Sufficiency score

For decision type `D` with ERP attributes `i`:

```text
S(E, D) = sum(w_i * e_i) / sum(w_i)
```

The decision may proceed only when:

```text
S(E, D) >= theta_D
and every required attribute has e_i >= minimum_score_i
```

`theta_D` is a configurable threshold. For example, a disease-treatment recommendation may require recent weather and disease-confidence evidence, while a general crop-information response may use a lower threshold.

### Evidence deficit priority

For each unsatisfied attribute:

```text
d_i = w_i * max(0, minimum_score_i - e_i)
priority_i = d_i * acquisition_cost_factor_i
```

The system returns missing evidence ordered by descending `priority_i`. The first implementation can request user input or retrieve an available data source; it should not invent absent evidence.

### Pseudocode

```text
load ERP for decision type D
score each required and optional evidence attribute
calculate S(E, D)
if S is below threshold or a required attribute fails:
    return INSUFFICIENT with ranked evidence deficits
return SUFFICIENT with decision-ready evidence
```

## A2 Decision State Construction

### Objective

Produce one auditable representation of the current farm situation after evidence is sufficient.

### Working

1. Select attributes whose ERP weight is at or above the inclusion floor.
2. Preserve the original values, normalized values, evidence score, confidence, and provenance.
3. Derive constraints, such as unsuitable rain window, unavailable irrigation, budget limit, safety restriction, or low-confidence diagnosis.
4. Store a normalized `context_vector` for later similarity matching.

No predictive model belongs in this step. This step prepares the facts and constraints used by ADIE-1.

## A3 ADIE-1 Agricultural Decision and Intervention Engine

### Objective

Generate feasible alternatives and select the action that best fits the current decision state, constraints, evidence quality, and similar prior outcomes.

### Candidate generation

For a decision type, actions come from a controlled action catalogue. Each action includes prerequisites, contraindications, expected cost, resource needs, safety limits, and applicable crops or conditions.

An action is feasible only when it passes hard constraints:

```text
feasible(a, x) = prerequisites_met AND budget_ok AND resource_ok
                 AND safety_ok AND weather_window_ok
```

### Context similarity

For current context `x` and historical ACER context `x_j`:

```text
dist(x, x_j) = sqrt(sum(k_m * (x_m - x_j)^2))
K(x, x_j) = exp(-(dist(x, x_j)^2) / (2 * sigma^2))
```

`k_m` gives important contextual dimensions more influence. Categorical dimensions use encoded equality or a category distance. Only records for the same action and compatible decision type are considered.

### Contextual effectiveness estimate

```text
mu_context(a, x) = sum(K(x, x_j) * observed_outcome_j) / sum(K(x, x_j))
mu(a, x) = (n_eff * mu_context(a, x) + lambda * mu_global(a)) / (n_eff + lambda)
```

`n_eff` is the sum of similarity weights. `lambda` prevents an estimate based on few records from dominating the decision. When no related ACER exists, use the catalog or model estimate `mu_global(a)` and explicitly label the low historical support.

### Action score

All terms are normalized to `[0, 1]`.

```text
score(a, x) = alpha * benefit(a, x)
            + beta  * mu(a, x)
            + gamma * evidence_confidence(x)
            - delta * risk(a, x)
            - epsilon * cost_penalty(a, x)
            - zeta * uncertainty(a, x)
```

Weights are decision-type specific and must sum to `1` after treating penalties as negative components. The explanation must show the winning score, rejected alternatives, constraints, evidence used, and historical support.

### Pseudocode

```text
input: decision state x, decision type D
retrieve feasible actions A
for each action a in A:
    retrieve contextually similar ACER records
    estimate contextual effectiveness mu(a, x)
    calculate score(a, x)
select highest-scoring action
record expected outcome, alternatives, evidence trace, and model versions
```

## A4 ACER Outcome Record

### Objective

Create a durable record that connects one decision to its real-world outcome.

### Working

When the farmer supplies an outcome, or a verified source provides it:

```text
deviation = observed_outcome - expected_outcome
```

The ACER stores the decision snapshot, action, context, expected outcome, observed outcome, deviation, feedback completeness, and outcome confidence. The system must distinguish a missing outcome from a poor outcome.

### Outcome confidence

```text
acer_confidence = outcome_measure_quality * feedback_completeness * evidence_sufficiency_at_decision
```

Only ACERs above a configured confidence floor can update the adaptive model automatically. Lower-confidence records remain available for review and analytics.

## A5 CNDA Contextual Deviation Attribution

### Objective

Identify context fields statistically associated with the deviation among similar records. CNDA means contextual deviation attribution; it is association-based, not a claim of causal proof.

### Working

1. Retrieve ACERs for the selected action near the current context.
2. For every contextual dimension, calculate its weighted association with deviation.
3. Select a factor only when support, association magnitude, and confidence exceed configured thresholds.

For numeric context feature `m`, use weighted correlation:

```text
c_m = weighted_correlation(x_m, deviation, K * acer_confidence)
association_confidence_m = min(1, n_eff / n_target) * abs(c_m)
```

For categorical factors, compare weighted mean deviation across category groups when each group has enough support. A factor becomes associated when:

```text
abs(c_m) >= correlation_threshold
and association_confidence_m >= confidence_threshold
and n_eff >= minimum_support
```

The response must say "associated with the deviation", not "caused the deviation".

## A6 Joint Adaptive Update

### Objective

Use the same qualified ACER to improve both future action evaluation and future evidence requirements.

### Action-context update

For an action `a` and stored context region `x`:

```text
mu_new(a, x) = mu_old(a, x) + eta_r * K(x, x_acer) * acer_confidence * deviation
```

Clamp the result to the valid outcome scale. The update moves the expected effectiveness toward the observed effectiveness, more strongly when contexts are similar and the outcome is credible. Maintain a weighted sample count and uncertainty estimate alongside the mean.

### ERP weight update

For each contextual factor `i` selected by CNDA:

```text
importance_i = association_confidence_i * min(1, abs(deviation) / deviation_scale)
w_i_new = clip(w_i_old + eta_w * importance_i, w_min, w_max)
```

For factors repeatedly not associated with meaningful deviations:

```text
w_i_new = max(w_min, w_i_old - decay_w)
```

After updates, normalize ERP weights within the decision type. Store a versioned update log with the ACER ID, old and new values, selected factors, and thresholds used.

### Safety rules

- Do not update from incomplete or low-confidence outcomes.
- Do not replace global behavior from one record; similarity, shrinkage, and sample support limit the change.
- Never use an adaptive update to bypass hard safety constraints.
- Keep every decision, ACER, and update auditable and reversible through version history.

## Development Order

1. Define database tables and JSON schemas for evidence, ERP, decision state, action catalogue, decision record, ACER, relationship aggregates, and update logs.
2. Implement A0 and A1 with fixed configuration files and deterministic tests.
3. Implement A2 and A3 with a small disease-intervention catalogue. Use the existing crop recommendation engine as one evidence source.
4. Implement A4, then connect the existing feedback screen to persist outcomes.
5. Implement A5 and A6 only after real ACER records can be created and retrieved.
6. Connect disease, fertilizer, irrigation, yield, and risk modules one at a time as evidence providers.
7. Run baseline experiments after the end-to-end path is complete.

## Evaluation Plan

Compare three systems using the same held-out or simulated decision sequence:

| System | Purpose |
| --- | --- |
| Static baseline | Uses current evidence but no contextual history or updates. |
| Context-aware non-adaptive baseline | Uses current context and historical records but does not update after outcomes. |
| AgroNexus adaptive system | Uses ERP, ADIE-1, ACER, CNDA, and joint updates. |

Measure expected-versus-observed outcome error, context-specific error, recommendation consistency, evidence retrieval/processing volume, sufficiency rate, computational time, and performance over sequential decision cycles.

## First Scope Boundary

The first end-to-end use case should be disease intervention for one crop family. It has a clear action catalogue, image-derived evidence, weather-sensitive context, an expected effectiveness value, and a farmer-observable outcome. Crop recommendation remains a useful existing evidence service, but it should not be the first adaptive intervention loop.
