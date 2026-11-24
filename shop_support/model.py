"""Chooses the model behind the agent from environment variables.

SHOP_MODEL                 what you get
-------------------------  ------------------------------------------------------------------
stand-in                   the scripted stand-in (no credentials, no network)
gemini-...                 Gemini through ADK's native client (GOOGLE_API_KEY or Vertex AI)
openai/<model name>        any OpenAI-compatible endpoint, through LiteLLM:
                             OPENAI_BASE_URL  e.g. https://api.openai.com/v1 or your own gateway
                             OPENAI_API_KEY   the key for that endpoint
<provider>/<model name>    any other LiteLLM provider prefix (anthropic/, ollama_chat/, ...)
"""
import os

DEFAULT_MODEL = "gemini-3.7-flash"


def build_model():
  name = os.environ.get("SHOP_MODEL") or DEFAULT_MODEL
  if name == "stand-in":
    from .standin import StandIn
    return StandIn()
  if "/" not in name:
    return name  # a Gemini model name, handled by ADK itself
  os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")  # no price-list download at import
  from google.adk.models.lite_llm import LiteLlm
  kwargs = {}
  if name.startswith("openai/"):
    if os.environ.get("OPENAI_BASE_URL"):
      kwargs["api_base"] = os.environ["OPENAI_BASE_URL"]
    if os.environ.get("OPENAI_API_KEY"):
      kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
  return LiteLlm(model=name, **kwargs)
