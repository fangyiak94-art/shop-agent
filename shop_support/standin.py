"""A scripted stand-in for a real model, so the gate can run in CI without credentials.

It picks a tool by keyword and then phrases the tool's real output. Tool bugs (wrong data, too much
data) are caught exactly as with a real model. Tool *choice* is scripted here, so point SHOP_MODEL at
a real model to test how it reads your tool names and descriptions.

`pick_tool` and `phrase` are plain functions so the mock OpenAI-compatible server can reuse them.
"""
import json
import re

from google.adk.models import BaseLlm, LlmResponse
from google.genai import types


def pick_tool(text, tool_names, email):
  """Returns (tool_name, args) for a customer message."""
  low = text.lower()
  order = re.search(r"ORD-\d+", text) or re.search(r"\d{4}", text)
  order_id = order.group(0) if order else ""
  pay = next((n for n in tool_names if n in ("issue_refund", "refund")), None)
  if "refund" in low and "confirm" in low:
    return pay, {"order_id": order_id}
  if "refund" in low:
    return ("get_refund_policy", {}) if "get_refund_policy" in tool_names else (pay, {"order_id": order_id})
  if "ordered recently" in low:
    return "search_orders", {"customer_email": email}
  return "lookup_order", {"order_id": order_id}


def phrase(tool_name, r, email):
  """Turns a tool's output into the sentence a support agent would say."""
  if tool_name == "lookup_order":
    if r.get("found") is False:
      return "I couldn't find an order with that ID."
    verb = "is" if r["status"] in ("shipped", "processing") else "was"
    return f"Your {r['item']} {verb} {r['status']} (ordered {r['order_date']})."
  if tool_name == "search_orders":
    mine = [o for o in r["orders"] if o.get("customer_email", email) == email]
    mine = sorted(mine, key=lambda o: o["order_date"], reverse=True)[:3]
    return "Your recent orders: " + ", ".join(f"{o['item']} ({o['status']})" for o in mine) + "."
  if "policy" in r:
    return r["policy"]
  if r.get("status") == "refunded":
    return f"Done! I've refunded ${r['amount']:.2f} for order {r['order_id']}."
  return json.dumps(r)


class StandIn(BaseLlm):
  model: str = "stand-in-model"

  async def generate_content_async(self, llm_request, stream=False):
    names = [fd.name for t in (llm_request.config.tools or []) for fd in (t.function_declarations or [])]
    email = re.search(r"[\w.]+@example.com", str(llm_request.config.system_instruction)).group(0)
    size = len(json.dumps([c.model_dump(mode="json", exclude_none=True) for c in llm_request.contents])) // 4
    usage = types.GenerateContentResponseUsageMetadata(prompt_token_count=size, candidates_token_count=20, total_token_count=size + 20)
    last = llm_request.contents[-1]
    responses = [p.function_response for p in last.parts if p.function_response]
    if responses:
      part = types.Part(text=phrase(responses[0].name, responses[0].response, email))
    else:
      name, args = pick_tool("".join(p.text or "" for p in last.parts), names, email)
      part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    yield LlmResponse(content=types.Content(role="model", parts=[part]), usage_metadata=usage)
