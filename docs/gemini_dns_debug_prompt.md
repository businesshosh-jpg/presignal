I need help diagnosing a Mac networking / DNS issue that is blocking a Python automation project.

Context:
- Machine: macOS
- Project path: `/Users/junhoshino/projects/presignal`
- The automation talks to Google APIs:
  - `oauth2.googleapis.com`
  - `sheets.googleapis.com`
- It used to work, then suddenly started failing.
- I am not using a VPN, proxy, or Private Relay.
- I already changed DNS servers to:
  - `1.1.1.1`
  - `8.8.8.8`
- I already rebooted the Mac.
- I also tried another network and still saw the same problem.

Current failure:
- Python automation fails before prediction logic starts.
- It dies during Google credential refresh / first Google API access.
- Representative errors:
  - `socket.gaierror: [Errno 8] nodename nor servname provided, or not known`
  - `Could not resolve host: oauth2.googleapis.com`
  - `Unable to find the server at sheets.googleapis.com`

Important diagnostic results:

1. Sometimes hostname lookup succeeds:
```bash
python3 -c "import socket; print(socket.getaddrinfo('oauth2.googleapis.com', 443)); print(socket.getaddrinfo('sheets.googleapis.com', 443))"
```
This has returned valid IPv4 and IPv6 addresses multiple times.

2. But real HTTPS access can still fail.

3. `curl` failed with:
```bash
curl -I https://oauth2.googleapis.com
curl: (6) Could not resolve host: oauth2.googleapis.com
```

4. Python HTTPS test also failed:
```bash
python3 -c "import requests; print(requests.get('https://oauth2.googleapis.com', timeout=10).status_code)"
```

5. I also tested with a separate Python 3.12 runtime, not just system Python 3.9:
```bash
/Users/junhoshino/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -c "import requests; print(requests.get('https://oauth2.googleapis.com', timeout=10).status_code)"
```
That failed the same way.

What has already been ruled out:
- Not just Python 3.9
- Not just the app code
- Not just Google auth token logic
- Not just IPv6
- Not just one Wi-Fi network

What I need from you:
1. Based on these symptoms, what is the most likely root cause on macOS?
2. What exact commands should I run next to diagnose machine-level DNS / resolver state?
3. What exact fixes should I try next, in order?
4. Is there a macOS resolver cache / DNS service / network extension issue that matches this pattern?

If useful, please suggest:
- `scutil --dns`
- `dscacheutil`
- `networksetup`
- `ifconfig`
- `route`
- `mDNSResponder`
- or any other concrete macOS-specific diagnostics

I want a step-by-step local debugging plan, not general networking advice.
