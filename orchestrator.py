import json
from services.claude_service import call_claude

VALID_INTENTS = {"ARB", "TIME", "MAPPING", "MATURITY", "INSIGHTS", "MULTI"}

ROUTING_SYSTEM_PROMPT = """You are an EA routing agent. Given a user query, respond with ONLY one of these exact strings:
ARB | TIME | MAPPING | MATURITY | INSIGHTS | MULTI

Routing rules:
- ARB: architecture review, approval, governance, standards, compliance, anti-pattern, proposal
- TIME: portfolio, rationalize, eliminate, invest, tolerate, migrate, retire, applications
- MAPPING: dependencies, impact, what breaks, coupling, integration, upstream, downstream
- MATURITY: maturity score, capability, assessment, EA gaps, how mature, EA practice
- INSIGHTS: optimize, executive summary, recommendations, cost savings, strategy, ROI, quick wins
- MULTI: query clearly needs 2 or more agents to answer completely

Respond with ONLY one word — no explanation, no punctuation."""

MULTI_CHAIN_SYSTEM_PROMPT = """You are an EA orchestration agent. Given a user query that requires multiple agents,
return a JSON array of agent names in the order they should be called.

Available agents: ARB, TIME, MAPPING, MATURITY, INSIGHTS

Rules:
- INSIGHTS almost always goes last (it synthesises other agents' outputs)
- MAPPING before ARB when dependency context is needed for a governance decision
- TIME before INSIGHTS for portfolio-level executive summaries
- Maximum 4 agents in a chain

Return ONLY a valid JSON array, e.g.: ["TIME", "MAPPING", "INSIGHTS"]
No explanation, no markdown."""


def route_request(query: str) -> str:
    """
    Use Claude to determine the intent of the user query.
    Returns one of: ARB | TIME | MAPPING | MATURITY | INSIGHTS | MULTI
    """
    user_message = f"User query: {query}"
    raw = call_claude(ROUTING_SYSTEM_PROMPT, user_message).strip().upper()

    # Extract the first word in case Claude adds punctuation
    intent = raw.split()[0].rstrip(".|,") if raw else "INSIGHTS"

    if intent not in VALID_INTENTS:
        # Fallback: default to INSIGHTS as a safe general-purpose agent
        intent = "INSIGHTS"

    return intent


def resolve_agents(intent: str, query: str) -> list:
    """
    Map an intent to an ordered list of agent names to invoke.
    For MULTI, calls Claude again to determine the optimal chain.
    """
    if intent != "MULTI":
        return [intent]

    # Ask Claude to determine the multi-agent chain
    user_message = f"User query that requires multiple agents: {query}"
    raw = call_claude(MULTI_CHAIN_SYSTEM_PROMPT, user_message).strip()

    # Strip markdown fences if present
    raw_clean = raw.lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        chain = json.loads(raw_clean)
        if isinstance(chain, list):
            # Validate all entries are known agents
            valid = {"ARB", "TIME", "MAPPING", "MATURITY", "INSIGHTS"}
            chain = [a.upper() for a in chain if a.upper() in valid]
            if chain:
                return chain
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: safe default multi-agent chain
    return ["TIME", "MAPPING", "INSIGHTS"]
