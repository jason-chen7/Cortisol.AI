"""Run this once to see which Gemini models your API key can access."""
import os
import httpx

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if not api_key:
    print("GEMINI_API_KEY not set")
    raise SystemExit(1)

resp = httpx.get(
    "https://generativelanguage.googleapis.com/v1/models",
    params={"key": api_key},
    timeout=10,
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    models = resp.json().get("models", [])
    print(f"\n{len(models)} models available:\n")
    for m in models:
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            print(f"  ✓  {m['name']}")
else:
    print(resp.text)
