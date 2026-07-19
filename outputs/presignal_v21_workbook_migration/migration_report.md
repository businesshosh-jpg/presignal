# PreSignal v2.1 Workbook Migration Report

## Decision

PASS. Both workbooks were built as inactive local artifacts. Source data was read through the existing authenticated Sheets client; no Sheets writes, Apps Script calls, or provider calls were made.

## Source Inventory

| Source | Fingerprint | Sheets | Hidden sheets | Named ranges | External links | Connections |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| auto_eeresults_predictions.xlsx (frozen lineage) | sha256:56ddc889f03e9d72a8f2e847c26cdb7a66f77162c07fe0d251675556ba7f7e20 | 19 | 0 | 0 | 0 | 0 |
| presignal_main.xlsx (provided seed) | sha256:8c78740e2f72668dfb543272a8593027c8139523e937b8921beb245d88e66e17 | 7 | 0 | 0 | 0 | 0 |
| presignal_research_diagnostics.xlsx | sha256:f9be19e3d21e7366ff9b4ea7db3c364520d5a67cc047e6128d84d90ce2e411b0 | 92 | 0 | 0 | 0 | 0 |
| presignal_research.xlsx (provided seed) | sha256:9b079c0cfa833704b49f8ef2940c76813771a8f5bacfc5655ee69836e82db4df | 1 | 0 | 0 | 0 | 0 |

The diagnostics workbook was inventoried only and none of its historical diagnostic sheets were migrated.

## Reusable Tables

| Sheet | Source rows | Target rows | Header count | Fingerprint |
| --- | ---: | ---: | ---: | --- |
| Event | 4316 | 4316 | 22 | sha256:b45ac9ffbbb5dcd03b1332b9170587a5d1d94ff58f65d91e6b37e125966535c9 |
| SeriesMap | 15 | 15 | 12 | sha256:6b8b75d894ad63a52efe019ccc018e29ce02be95a2cb046c48d173c3fb7a2092 |
| FRED_Series_ID | 533 | 533 | 16 | sha256:01c1c15d4dcf8a4c70e625ce0cfdc41c60af9349760e19978fa42827a31ac667 |
| FMP_EventCatalog | 289 | 289 | 25 | sha256:8deeafe6c0e2dd99e374698ab7b55cd2fa30e169ee350846083de378cfcb25f6 |

## Config Decisions

| config_key | source_value_present | migration_status | target_value | reason |
| --- | --- | --- | --- | --- |
| Google Sheet Authorization | FALSE | NOT_APPLICABLE |  | Section label, not a configuration value. |
| MAIN_WORKBOOK_ID | TRUE | RESET | INACTIVE_PLACEHOLDER | Workbook routing is intentionally inactive pending an approved cutover. |
| DIAGNOSTICS_WORKBOOK_ID | TRUE | RESET | INACTIVE_PLACEHOLDER | Workbook routing is intentionally inactive pending an approved cutover. |
| ARCHIVE_01_WORKBOOK_ID | TRUE | RESET | INACTIVE_PLACEHOLDER | Workbook routing is intentionally inactive pending an approved cutover. |
| OVERVIEW_WORKBOOK_ID | TRUE | RESET | INACTIVE_PLACEHOLDER | Workbook routing is intentionally inactive pending an approved cutover. |
| - EVENT- | FALSE | NOT_APPLICABLE |  | Section label, not a configuration value. |
| WINDOW_ENABLED | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| WINDOW_FROM_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| WINDOW_TO_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| SYSTEM_TIMEZONE | TRUE | RENAMED | UTC | Retains the common operating timezone without retaining prediction-window behavior. |
| - PREDICTION - | FALSE | NOT_APPLICABLE |  | Section label, not a configuration value. |
| PRED_MAX_WORK_UNITS_PER_RUN | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PRED_RESUME_ENABLED | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PRED_AUTO_CONTINUE_ENABLED | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PRED_AUTO_CONTINUE_DELAY_SEC | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PRED_AUTO_CONTINUE_DELAY_MIN | FALSE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PROVIDERS | TRUE | MIGRATED | OpenAI,Gemini,Anthropic | Reusable source, provider, model, mapping, or foundation setting. |
| PREDICTION_MODE | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PREDICTION_TEMPERATURE | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PREDICTION_SEED | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| PRED_WINDOW_ENABLED | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| PRED_WINDOW_FROM_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| PRED_WINDOW_TO_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| PRED_WINDOW_TZ | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| < Provider Specific > | FALSE | NOT_APPLICABLE |  | Section label, not a configuration value. |
| CLAUDE_MODEL | TRUE | MIGRATED | claude-haiku-4-5 | Reusable source, provider, model, mapping, or foundation setting. |
| ANTHROPIC_PROMPT_CACHE_ENABLED | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| ANTHROPIC_PROMPT_CACHE_TTL | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| - MARKET REACTION - | FALSE | NOT_APPLICABLE |  | Section label, not a configuration value. |
| MR_PRIMARY_PROVIDER | TRUE | MIGRATED | tiingo | Reusable source, provider, model, mapping, or foundation setting. |
| MR_COMPARE_PROVIDER | TRUE | MIGRATED | eodhd | Reusable source, provider, model, mapping, or foundation setting. |
| MR_COMPARE_PROVIDER_2 | TRUE | MIGRATED | massive | Reusable source, provider, model, mapping, or foundation setting. |
| MR_COMPARE_PROVIDER_3 | TRUE | MIGRATED | twelvedata | Reusable source, provider, model, mapping, or foundation setting. |
| MR_WINDOW_ENABLED | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| MR_WINDOW_FROM_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| MR_WINDOW_TO_LOCAL | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| MR_WINDOW_TZ | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| MR_HORIZON_MIN | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| MR_ANCHOR_MIN_ABS_MOVE_PIPS | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| MR_ANCHOR_LOOKBACK_MIN | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| MR_ANCHOR_LOOKAHEAD_MIN | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| MR_SKIP_ALREADY_SCORED | TRUE | RETIRED |  | Not needed for the clean v2.1 workbook foundation. |
| MR_FLAT_MAX_ABS_PIPS | TRUE | RETIRED |  | Legacy experiment, replay, repair, scoring, or window setting. |
| PRESIGNAL_MAIN_WORKBOOK_ID | FALSE | RESET | INACTIVE_PLACEHOLDER | Inactive destination identifier placeholder. |
| PRESIGNAL_RESEARCH_WORKBOOK_ID | FALSE | RESET | INACTIVE_PLACEHOLDER | Inactive destination identifier placeholder. |

## Fresh Tables

The following main-workbook tables contain headers only: SeriesMap_Suggestions, Episode, Information, Prediction, Prediction_Path, Outcome, Evaluation, Session_Map, Run_Log. The research workbook contains only its five required header-only tables.

## Sanitization

| Target | Formulas | External links | Connections | Hidden sheets | Named ranges |
| --- | ---: | ---: | ---: | ---: | ---: |
| presignal_main.xlsx | 0 | 0 | 0 | 0 | 0 |
| presignal_research.xlsx | 0 | 0 | 0 | 0 | 0 |

## Validation

All target validation checks passed: main_exact_sheet_inventory, research_exact_sheet_inventory, main_no_prohibited_sheets, main_no_hidden_sheets, research_no_hidden_sheets, main_no_external_links, research_no_external_links, main_no_connections, research_no_connections, main_no_named_ranges, research_no_named_ranges, main_no_formulas, research_no_formulas, fresh_main_tables_headers_only, research_tables_headers_only, schema_has_inheritance_rows, node_builder_reported_expected_sheets.
