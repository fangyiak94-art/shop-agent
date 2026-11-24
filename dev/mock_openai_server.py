"""A tiny OpenAI-compatible server (POST /v1/chat/completions) for trying the agent without an API key.

It speaks the real wire format (messages, tools, tool_calls, usage) and answers with the same scripted
logic as the stand-in model. Use it to prove the OpenAI-compatible path end to end:

    python dev/mock_openai_server.py 8900 &
    SHOP_MODEL=openai/mock OPENAI_BASE_URL=http://127.0.0.1:8900/v1 OPENAI_API_KEY=anything \
        pytest tests/test_trace_gate.py -q
"""
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, ".")
from shop_support.standin import phrase, pick_tool


def text_of(content):
  if isinstance(content, list):
    return "".join(p.get("text", "") for p in content if isinstance(p, dict))
  return content or ""


class Handler(BaseHTTPRequestHandler):
  def log_message(self, *args):
    pass

  def do_POST(self):
    body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
    messages, tools = body.get("messages", []), body.get("tools") or []
    names = [t["function"]["name"] for t in tools]
    system = " ".join(text_of(m.get("content")) for m in messages if m["role"] in ("system", "developer"))
    found = re.search(r"[\w.]+@example.com", system)
    email = found.group(0) if found else ""
    last = messages[-1]
    if last["role"] == "tool":
      called = {c["id"]: c["function"]["name"] for m in messages for c in (m.get("tool_calls") or [])}
      message = {"role": "assistant", "content": phrase(called.get(last.get("tool_call_id"), ""), json.loads(text_of(last["content"])), email)}
      finish = "stop"
    else:
      name, args = pick_tool(text_of(last.get("content")), names, email)
      message = {"role": "assistant", "content": None,
                 "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
      finish = "tool_calls"
    prompt_tokens = len(json.dumps(messages)) // 4
    reply = {"id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()), "model": body.get("model", "mock"),
             "choices": [{"index": 0, "message": message, "finish_reason": finish}],
             "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 20, "total_tokens": prompt_tokens + 20}}
    data = json.dumps(reply).encode()
    self.send_response(200)
    self.send_header("content-type", "application/json")
    self.send_header("content-length", str(len(data)))
    self.end_headers()
    self.wfile.write(data)


if __name__ == "__main__":
  port = int(sys.argv[1]) if len(sys.argv) > 1 else 8900
  print(f"mock OpenAI-compatible server on http://127.0.0.1:{port}/v1")
  ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
