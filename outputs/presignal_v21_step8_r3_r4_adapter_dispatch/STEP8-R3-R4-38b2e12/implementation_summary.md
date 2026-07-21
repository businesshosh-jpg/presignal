# Step 8-R3-R4 Adapter Dispatch

The existing R3 dispatcher now persists immutable stage payloads and results around the concrete lineage, forecast, Outcome, and evaluation functions.

The one-Episode live smoke processed `EP_BATCH_b5c0c544ec07bbf0b950` only. It made five provider calls: Anthropic Attention was rejected for a truncated raw JSON response; Gemini and OpenAI Attention were accepted, and their Information Requests were strictly rejected for invalid request enums. No request was retried, no forecast call was made, no Outcome was read, and resume issued no duplicate call.

This validates durable adapter dispatch and terminal handling. The smoke does not establish provider completion quality or forecast accuracy.
