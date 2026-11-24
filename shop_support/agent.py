"""Support agent for an online shop. Run it with `adk web` from the repo root."""
from google.adk.agents import Agent

from .db import build_database
from .model import build_model
from .tools import TOOLS

INSTRUCTION = """You are the support assistant for an online shop.
The signed-in customer is {customer_email?}.
Use the tools to answer questions about orders and refunds. Be brief and friendly."""

build_database()

root_agent = Agent(name="support_agent", model=build_model(), instruction=INSTRUCTION, tools=TOOLS)
