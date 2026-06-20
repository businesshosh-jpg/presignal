# PreSignal Compass (Function-Based Architecture)

## Core Vision

PreSignal is evolving into two parallel intelligence systems:

```text
Forecast Intelligence
+
Character Intelligence
```

These systems have different purposes and should be evaluated separately.

---

# System A - Forecast Intelligence Engine

Purpose:

```text
Predict economic outcomes
as accurately as possible.
```

This is the mainstream forecasting branch.

Architecture:

```text
Economic Data
↓
Historical Memory Layer
↓
Event Context Layer
↓
Market Regime Layer
↓
Forecast Engine
↓
Evaluation
↓
Learning
↓
Calibration
↓
Forecast
```

## Historical Memory Layer

Purpose:

```text
Provide historical event memory.
```

Contains:

- Same-indicator history
- Historical actual values
- Historical outcome patterns
- Event memory

Equivalent to the original historical-context work.

## Event Context Layer

Purpose:

```text
Expand event-specific information.
```

Contains:

- Surprise history
- Revision history
- Family relationships
- Signal-quality diagnostics

Former implementation:

```text
Feature Pack v2A
```

Use the functional name instead.

## Market Regime Layer

Purpose:

```text
Describe the market environment
before the release occurs.
```

Contains:

- Fed Funds
- DFF
- US2Y
- US10Y
- Yield Curve
- JP10Y
- USDJPY
- DXY
- SPX
- Gold
- WTI

Former implementation:

```text
Feature Pack v2B
```

Use the functional name instead.

## Forecast Learning Layer

Future research.

Purpose:

```text
Determine which information
actually improves forecasts.
```

Possible future outputs:

- Feature importance
- Regime adaptation
- Provider adaptation
- Context selection

## Forecast Calibration Layer

Future research.

Purpose:

```text
Adjust forecast behavior
based on measured outcomes.
```

Examples:

- Confidence adjustment
- Forecast magnitude adjustment
- Regime-aware corrections

---

# System B - Character Intelligence Engine

Purpose:

```text
Measure recurring differences
between intelligent observers.
```

This is not a forecasting engine.

It is a signal-discovery engine.

Architecture:

```text
Forecast Outputs
↓
Character Residual Layer
↓
Character Recurrence Layer
↓
Provider Character Economic Validation Branch
↓
Character Drift Layer
↓
Economic Shadow Test Layer
```

## Character Residual Layer

Purpose:

```text
Measure provider behavior
relative to deterministic expectations.
```

Produces:

- Residual vectors
- Factor emphasis
- Risk language
- Uncertainty patterns

## Character Recurrence Layer

Purpose:

```text
Determine whether provider
behaviors recur over time.
```

Question:

```text
Does the behavior repeat?
```

## Provider Character Economic Validation Branch

Purpose:

```text
Determine whether recurring
provider character traits
correlate with Economic Value
outcomes.
```

This is the active character research branch.

It includes:

- Economic Outcome Link
- Economic Falsification
- Economic Recurrence
- Economic Shadow Test

The retired branches `Character → Market Reaction Outcome`, `Character → Reliability Outcome`, and `Character → Calibration Candidate` are no longer active. Future character work should evaluate against Economic Value outcomes only unless a later roadmap revision explicitly re-opens a different axis.

## Character Drift Layer

Purpose:

```text
Determine whether providers
change over time.
```

Question:

```text
Did the detector move?
```

## Character Signal Layer

Retired as a tabbed workstream; keep only as a conceptual placeholder unless a later governance revision explicitly reopens it.

Purpose:

```text
Convert validated,
economic-value-linked
character behavior
into candidate meta-signals.
```

The earlier `Character_Signal_*` sheets were retired and removed. Any future reopen must be rebuilt against Economic Value outcomes only.

Important:

```text
Character Signal
≠
Forecast Signal
```

This distinction remains unproven.

## Economic Shadow Test Layer

Current active branch.

Purpose:

```text
Test whether validated
economic-character candidates
would have separated better
economic outcomes from worse
economic outcomes in shadow mode.
```

This layer bridges:

- Provider Character Economic Validation Branch
- Forecast Reliability Layer
- future Character-Assisted Calibration research

It does not change live predictions.

---

# System C - Meta Intelligence Layer

Purpose:

```text
Combine forecast information
and character information.
```

Architecture:

```text
Forecast Intelligence
+
Character Intelligence
↓
Meta Intelligence
↓
Final Forecast Decision
```

## Forecast Reliability Layer

Most likely first use of Character.

Purpose:

```text
Estimate forecast reliability.
```

Questions:

```text
Should this forecast be trusted?

Is this event unusual?

Are providers behaving normally?
```

## Character-Assisted Calibration Layer

Long-term research.

Purpose:

```text
Use validated Character Signals
to improve forecasting behavior.
```

Requirements:

- Character recurrence proven
- Character outcome value proven
- Drift understood
- Calibration value proven

Not yet achieved.

---

# Current Research Status

## Forecast Intelligence

```text
Historical Memory Layer
✓

Event Context Layer
✓

Market Regime Layer
✓

Replay-Safe Infrastructure
✓

Forecast Learning
In Progress

Forecast Calibration
Future
```

## Character Intelligence

```text
Character Residuals
✓

Character Recurrence
✓

Provider Character Economic Validation Branch
In Progress

Character Falsification
✓

Character Drift Validation
✓

Character Signals
Retired

Character Signal Candidates
Retired

Character Signal Shadow Test
Retired

Economic Shadow Test
In Progress

Character-Assisted Calibration
Unproven
```

---

# Guiding Philosophy

Old vision:

```text
Build a better predictor.
```

Current vision:

```text
Build a better predictor

and

Build a system that understands
when that predictor should
or should not be trusted.
```

---

# Long-Term Compass

```text
Historical Memory
+
Event Context
+
Market Regime Context
↓
Forecast Intelligence
```

parallel with

```text
Character Residuals
+
Recurrence
+
Economic Validation
+
Drift Monitoring
↓
Character Intelligence
```

feeding into

```text
Meta Intelligence
↓
Forecast Reliability
↓
Character-Assisted Calibration
↓
Final Forecast
```

This structure avoids version-name confusion because the roadmap is organized around what each layer does, not when it happened to be built. Future implementations can still have version numbers internally, but the architecture remains understandable even years later.
