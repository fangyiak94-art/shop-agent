"""Support agent for an online shop. Run it with `adk web` from the repo root."""
import os

from google.adk.agents import Agent

from .db import build_database
from .tools import TOOLS

MODEL_NAME = os.environ.get("SHOP_MODEL", "gemini-3.7-flash")
if MODEL_NAME == "stand-in":
  from .standin import StandIn
  MODEL = StandIn()
else:
  MODEL = MODEL_NAME

INSTRUCTION = """You are the support assistant for an online shop.
The signed-in customer is {customer_email?}.
Use the tools to answer questions about orders and refunds. Be brief and friendly."""

build_database()

root_agent = Agent(name="support_agent", model=MODEL, instruction=INSTRUCTION, tools=TOOLS)
