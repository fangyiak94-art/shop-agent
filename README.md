# shop-agent: a support agent with a trace gate in CI

A small support agent (Google ADK) plus a CI check that runs five golden questions on every pull request
and inspects the **trace** of each run. A change can only merge if every question passes three kinds of check:

| Check | Asks | Reads from the trace |
|---|---|---|
| `[tool]` | Did the agent call the right tool, and none it must not? | tool calls on the model spans |
| `[answer]` / `[privacy]` | Is the answer built on the right data, and only this customer's? | tool responses, final answer |
| `[budget]` | Did it stay within token and payload limits? | `gen_ai.usage.input_tokens`, tool response size |

## Run it

```bash
pip install -r requirements.txt
SHOP_MODEL=stand-in pytest tests/test_trace_gate.py -q
```

`SHOP_MODEL=stand-in` uses a scripted model so the gate runs without credentials. Tool bugs are caught exactly
as with a real model; tool *choice* is scripted. To gate on real Gemini, set `SHOP_MODEL` to a model name and
provide `GOOGLE_API_KEY`.

## Layout

- `shop_support/` - the agent, its tools and the shop database
- `tests/golden.py` - the golden questions and budgets
- `tests/trace_harness.py` - runs the agent, captures telemetry in memory, turns the trace into facts
- `tests/test_trace_gate.py` - the gate
- `.github/workflows/trace-gate.yml` - runs the gate on every pull request and attaches failing traces
