"""Use a running loopback EviWeave service with Python's standard library."""
import json
import os
import urllib.request


def request(path, payload):
    headers = {"Content-Type": "application/json"}
    token = os.getenv("EVIWEAVE_API_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    call = urllib.request.Request("http://127.0.0.1:18403" + path,
                                  data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(call, timeout=120) as response:
        return json.load(response)


if __name__ == "__main__":
    print(request("/add", dict(user_id="demo", request_id="example-1", session_id="demo-session",
                               messages=[dict(role="user", content="Luna prefers the blue feather wand.")])))
    print(json.dumps(request("/search", dict(user_id="demo", query="Luna wand", top_k=5)),
                     indent=2, ensure_ascii=False))
