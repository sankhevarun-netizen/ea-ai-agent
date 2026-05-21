import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_supabase_client = None


def _get_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception:
        return None


def fetch_applications() -> list:
    """Fetch all applications from the portfolio."""
    try:
        client = _get_client()
        if not client:
            return []
        result = client.table("applications").select("*").execute()
        return result.data or []
    except Exception:
        return []


def fetch_recent_decisions(limit: int = 5) -> list:
    """Fetch the most recent architecture decisions for memory injection."""
    try:
        client = _get_client()
        if not client:
            return []
        result = (
            client.table("architecture_decisions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def fetch_standards_rules() -> list:
    """Fetch enterprise architecture standards and governance rules."""
    try:
        client = _get_client()
        if not client:
            return []
        result = client.table("standards_rules").select("*").execute()
        return result.data or []
    except Exception:
        return []


def fetch_maturity_scores() -> list:
    """Fetch historical maturity assessment scores."""
    try:
        client = _get_client()
        if not client:
            return []
        result = (
            client.table("maturity_scores")
            .select("*")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return result.data or []
    except Exception:
        return []


def fetch_dependencies(app_id: str = None) -> list:
    """Fetch application dependency mappings, optionally filtered by app_id."""
    try:
        client = _get_client()
        if not client:
            return []
        query = client.table("dependencies").select("*")
        if app_id:
            query = query.eq("source_app_id", app_id)
        result = query.execute()
        return result.data or []
    except Exception:
        return []


def store_decision(input_data: dict, output_data: str, agent: str) -> None:
    """Persist agent input/output to architecture_decisions for memory continuity."""
    try:
        client = _get_client()
        if not client:
            return
        client.table("architecture_decisions").insert({
            "agent": agent,
            "input_data": json.dumps(input_data),
            "output_data": output_data,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def fetch_integration_patterns() -> list:
    """Fetch known integration patterns for mapping context."""
    try:
        client = _get_client()
        if not client:
            return []
        result = client.table("integration_patterns").select("*").execute()
        return result.data or []
    except Exception:
        return []
