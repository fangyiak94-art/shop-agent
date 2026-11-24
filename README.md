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

## Choosing the model

The agent reads its model from environment variables (`shop_support/model.py`):

| `SHOP_MODEL` | Model behind the agent | Also set |
|---|---|---|
| `stand-in` | A scripted stand-in. No credentials, no network. Tool bugs are caught as with a real model; tool *choice* is scripted | nothing |
| `openai/<model>` | Any OpenAI-compatible endpoint, through LiteLLM | `OPENAI_BASE_URL`, `OPENAI_API_KEY` |
| `gemini-...` | Gemini, through ADK's native client | `GOOGLE_API_KEY` |

```bash
# a real OpenAI-compatible provider
SHOP_MODEL=openai/gpt-4o-mini OPENAI_BASE_URL=https://api.openai.com/v1 OPENAI_API_KEY=sk-... \
  pytest tests/test_trace_gate.py -q

# no key? prove the OpenAI-compatible path against the bundled mock endpoint
python dev/mock_openai_server.py 8900 &
SHOP_MODEL=openai/mock OPENAI_BASE_URL=http://127.0.0.1:8900/v1 OPENAI_API_KEY=anything \
  pytest tests/test_trace_gate.py -q
```

In CI, set `SHOP_MODEL` and `OPENAI_BASE_URL` as repository variables and `OPENAI_API_KEY` as a repository secret.
With none set, the workflow uses the stand-in.

## Layout

- `shop_support/` - the agent, its tools, the shop database and the model switch (`model.py`)
- `dev/mock_openai_server.py` - a tiny OpenAI-compatible endpoint for trying the agent without a key
- `tests/golden.py` - the golden questions and budgets
- `tests/trace_harness.py` - runs the agent, captures telemetry in memory, turns the trace into facts
- `tests/test_trace_gate.py` - the gate
- `.github/workflows/trace-gate.yml` - runs the gate on every pull request and attaches failing traces
