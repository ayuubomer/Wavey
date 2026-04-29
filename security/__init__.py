"""
security/__init__.py — public surface.

app.py should only ever need:
    from security import analyze_query, SecurityResult, Decision
"""
from .pipeline import analyze_query
from .models   import SecurityResult, Decision

__all__ = ["analyze_query", "SecurityResult", "Decision"]