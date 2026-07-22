# Shared Runtime Reliability

The historical synchronized failures happened before the provider bridge, on the common Google credential refresh and Apps Script Execution API path. The repaired runtime serializes token refresh, writes tokens atomically, uses a harmless health endpoint, and refuses future admission when authentication or health is not ready. No provider was called.
