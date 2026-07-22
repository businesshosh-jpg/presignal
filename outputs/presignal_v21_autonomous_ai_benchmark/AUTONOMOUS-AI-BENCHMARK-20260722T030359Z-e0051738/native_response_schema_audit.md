# Native Response Schema Audit

`EXISTING_RESPONSES_RECOVERABLE_WITH_DETERMINISTIC_PARSE`

Nine responses cannot be normalized because `confidence` is an unspecified ordinal (`Medium`, `2`, or `3`) while the frozen parser requires numeric `[0,1]`. One explicit no-signal response is deterministically compatible after call-binding identity recovery and no-signal canonicalization.

| Episode | Rejection | Recoverable |
|---|---|---|
| EP_EVENT_58e1701b15c0178692ba | PROVIDER_OUTPUT_TYPES | False |
| EP_EVENT_053c10a3d4a69d6881af | PROVIDER_OUTPUT_CONFIDENCE | False |
| EP_BATCH_6a6fe55ba8eff4d3ce2c | PROVIDER_OUTPUT_CONFIDENCE | False |
| EP_EVENT_b5f2d28b12e37e2d9b72 | PROVIDER_OUTPUT_NO_SIGNAL_PATH | True |
| EP_EVENT_64e72292b54cab80cc69 | PROVIDER_OUTPUT_CONFIDENCE | False |
| EP_BATCH_5db4a9668cccb78d621e | PROVIDER_OUTPUT_TYPES | False |
| EP_EVENT_2de77b689facc34d5811 | PROVIDER_OUTPUT_TYPES | False |
| EP_EVENT_5a1719c3db61418e808e | PROVIDER_OUTPUT_TYPES | False |
| EP_EVENT_28649186b338eb5b0a22 | PROVIDER_OUTPUT_TYPES | False |
| EP_EVENT_3f0ac9fb4f1a138fee7f | PROVIDER_OUTPUT_CONFIDENCE | False |
