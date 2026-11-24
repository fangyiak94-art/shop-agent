"""Runs the agent once, captures its telemetry in memory, and turns the trace into facts a test can assert on."""
import asyncio
import json
import os
import re

os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "EVENT_ONLY")
os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

from opentelemetry import _logs, trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SPANS = InMemorySpanExporter()
LOGS = InMemoryLogRecordExporter()
_tp = TracerProvider(); _tp.add_span_processor(SimpleSpanProcessor(SPANS)); trace.set_tracer_provider(_tp)
_lp = LoggerProvider(); _lp.add_log_record_processor(SimpleLogRecordProcessor(LOGS)); _logs.set_logger_provider(_lp)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shop_support.agent import root_agent
from shop_support.db import build_database, refunds_paid


class Trace:
  """One agent run, as read from its spans and events."""

  def __init__(self, question, answer, spans, logs):
    self.question, self.answer = question, answer
    self.spans = sorted(spans, key=lambda s: s.start_time)
    events = {l.log_record.span_id: (l.log_record.attributes or {}) for l in logs}
    self.model_calls, self.tool_calls, self.tool_responses = [], [], []
    for s in self.spans:
      if s.name.startswith("generate_content"):
        self.model_calls.append({"input_tokens": s.attributes.get("gen_ai.usage.input_tokens", 0)})
        ev = events.get(s.context.span_id, {})
        for m in ev.get("gen_ai.output.messages", ()):
          for p in m.get("parts", ()):
            if p.get("type") == "tool_call":
              self.tool_calls.append({"name": p["name"], "args": dict(p.get("arguments") or {})})
        # Each model call's input repeats the whole conversation so far, so the last call's
        # input holds every tool response exactly once, in order.
        seen = [p.get("response") for m in ev.get("gen_ai.input.messages", ()) for p in m.get("parts", ())
                if p.get("type") == "tool_call_response"]
        if len(seen) >= len(self.tool_responses):
          self.tool_responses = seen
    self.tools_called = [c["name"] for c in self.tool_calls]

  def render(self):
    """A short text view of the trace, attached to a failing check."""
    depth, lines, n_tool = {}, [], 0
    for s in self.spans:
      d = depth[s.context.span_id] = (depth.get(s.parent.span_id, -1) + 1) if s.parent else 0
      extra = []
      if "gen_ai.usage.input_tokens" in s.attributes:
        extra.append(f"input_tokens={s.attributes['gen_ai.usage.input_tokens']:,}")
      if "shop.rows_returned" in s.attributes:
        extra.append(f"shop.rows_returned={s.attributes['shop.rows_returned']}")
      lines.append("  " * d + s.name + (f"   [{', '.join(extra)}]" if extra else ""))
      if s.name.startswith("execute_tool") and n_tool < len(self.tool_calls):
        call = self.tool_calls[n_tool]
        lines.append("  " * d + f"    args:     {json.dumps(call['args'])}")
        if n_tool < len(self.tool_responses):
          body = json.dumps(self.tool_responses[n_tool])
          lines.append("  " * d + f"    returned: {body[:140]}{'...' if len(body) > 140 else ''}   ({len(body):,} chars)")
        n_tool += 1
    return "\n".join(lines)


def run_case(question, customer):
  """Fresh database, one question, one captured trace."""
  build_database()
  SPANS.clear(); LOGS.clear()

  async def go():
    sessions = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="shop_support", session_service=sessions)
    session = await sessions.create_session(app_name="shop_support", user_id=customer, state={"customer_email": customer})
    answer = ""
    with trace.get_tracer("trace-gate").start_as_current_span("golden_question"):
      async for event in runner.run_async(user_id=customer, session_id=session.id,
                                          new_message=types.Content(role="user", parts=[types.Part(text=question)])):
        if event.is_final_response() and event.content and event.content.parts:
          # Thinking models return their reasoning as parts marked `thought`; the customer never sees those.
          answer = "".join(p.text or "" for p in event.content.parts if not getattr(p, "thought", False))
    return answer

  answer = asyncio.run(go())
  return Trace(question, answer, SPANS.get_finished_spans(), LOGS.get_finished_logs())


def check(case, tr, budget, customer):
  """Returns a list of violations. Empty means the change may merge."""
  v = []
  # 1. Right tool?
  # The expected tools must be called, in this order. A real model may take extra, harmless steps
  # (look an order up before refunding it), so other tools are allowed unless a case forbids them.
  remaining = iter(tr.tools_called)
  if not all(name in remaining for name in case["expect_tools"]):
    v.append(f"[tool]    expected tools {case['expect_tools']} (in order), the agent called {tr.tools_called}")
  for name in case.get("forbid_tools", ()):
    if name in tr.tools_called:
      v.append(f"[tool]    forbidden tool was called: {name}")
  # 2. Right answer, built on the right data?
  for needle in case.get("answer_contains", ()):
    if needle.lower() not in tr.answer.lower():
      v.append(f"[answer]  expected the answer to mention {needle!r}, got: {tr.answer[:120]!r}")
  for key, want in case.get("tool_response_has", {}).items():
    got = [r.get(key) for r in tr.tool_responses if isinstance(r, dict)]
    if want not in got:
      v.append(f"[answer]  expected a tool response with {key}={want!r}, got {got}")
  if "refunds_paid" in case and len(refunds_paid()) != case["refunds_paid"]:
    v.append(f"[answer]  expected {case['refunds_paid']} refund(s) in the database, found {len(refunds_paid())}: {refunds_paid()}")
  others = sorted({e for r in tr.tool_responses for e in re.findall(r"[\w.]+@example\.com", json.dumps(r)) if e != customer})
  if others:
    v.append(f"[privacy] tool responses expose {len(others)} other customer(s), e.g. {others[0]}")
  # 3. Within budget?
  for i, m in enumerate(tr.model_calls, 1):
    if m["input_tokens"] > budget["max_input_tokens"]:
      v.append(f"[budget]  model call {i} used {m['input_tokens']:,} input tokens (limit {budget['max_input_tokens']:,})")
  for r in tr.tool_responses:
    size = len(json.dumps(r))
    if size > budget["max_tool_response_chars"]:
      v.append(f"[budget]  a tool returned {size:,} characters (limit {budget['max_tool_response_chars']:,})")
  return v
