"""A scripted stand-in for Gemini, so the gate can run in CI without credentials.

It picks a tool by keyword and then phrases the tool's real output. Tool bugs (wrong data, too much
data) are caught exactly as with a real model. Tool *choice* is scripted here, so set SHOP_MODEL to a
real Gemini model to test how the model reads your tool names and descriptions.
"""
import json
import re

from google.adk.models import BaseLlm, LlmResponse
from google.genai import types


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
      r, name = responses[0].response, responses[0].name
      if name == "lookup_order":
        if r.get("found") is False:
          text = "I couldn't find an order with that ID."
        else:
          verb = "is" if r["status"] in ("shipped", "processing") else "was"
          text = f"Your {r['item']} {verb} {r['status']} (ordered {r['order_date']})."
      elif name == "search_orders":
        mine = [o for o in r["orders"] if o.get("customer_email", email) == email]
        mine = sorted(mine, key=lambda o: o["order_date"], reverse=True)[:3]
        text = "Your recent orders: " + ", ".join(f"{o['item']} ({o['status']})" for o in mine) + "."
      elif "policy" in r:
        text = r["policy"]
      elif r.get("status") == "refunded":
        text = f"Done! I've refunded ${r['amount']:.2f} for order {r['order_id']}."
      else:
        text = json.dumps(r)
      yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]), usage_metadata=usage)
      return
    text = "".join(p.text or "" for p in last.parts)
    order = (re.search(r"ORD-\d+", text) or re.search(r"\d{4}", text))
    order_id = order.group(0) if order else ""
    pay = next((n for n in names if n in ("issue_refund", "refund")), None)
    if "refund" in text.lower() and "confirm" in text.lower():
      call = (pay, {"order_id": order_id})
    elif "refund" in text.lower():
      call = ("get_refund_policy", {}) if "get_refund_policy" in names else (pay, {"order_id": order_id})
    elif "ordered recently" in text.lower():
      call = ("search_orders", {"customer_email": email})
    else:
      call = ("lookup_order", {"order_id": order_id})
    part = types.Part(function_call=types.FunctionCall(name=call[0], args=call[1]))
    yield LlmResponse(content=types.Content(role="model", parts=[part]), usage_metadata=usage)
