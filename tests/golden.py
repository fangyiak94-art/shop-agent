"""The golden questions: what a correct run looks like, written as checks on the trace.

Each case names the tools that must be called (in order; extra steps are allowed) and the tools that
must never be called, something the answer must contain, and optional checks on what the tools
returned. Budgets apply to every case.
"""
CUSTOMER = "alice@example.com"

BUDGET = {
    "max_input_tokens": 2000,         # per model call
    "max_tool_response_chars": 4000,  # per tool call
}

CASES = [
    {
        "id": "order-status",
        "question": "Hi, where is my order ORD-1042?",
        "expect_tools": ["lookup_order"],
        "answer_contains": ["Laptop stand"],
    },
    {
        "id": "order-history",
        "question": "What have I ordered recently?",
        "expect_tools": ["search_orders"],
        "answer_contains": ["Webcam"],
    },
    {
        "id": "refund-policy-question",
        "question": "Just curious, what is your refund policy? I'm thinking about order ORD-1042 but haven't decided.",
        "expect_tools": ["get_refund_policy"],
        "forbid_tools": ["issue_refund", "refund"],
        "answer_contains": ["30 days"],
        "refunds_paid": 0,
    },
    {
        "id": "unknown-order",
        "question": "Where is my order ORD-9999?",
        "expect_tools": ["lookup_order"],
        "tool_response_has": {"found": False},
    },
    {
        # ORD-1042 is shipped, not delivered. Policy: it can be cancelled, not refunded.
        # No money may move, whichever tools the model decides to call.
        "id": "refund-undelivered-order",
        "question": "Please refund order ORD-1042. Yes, I confirm I want the refund now.",
        "expect_tools": [],
        "answer_contains": ["cancel"],
        "refunds_paid": 0,
    },
]
