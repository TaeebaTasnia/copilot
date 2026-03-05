"""
Router
======
Decides which agent handles a query using a simple keyword check.
No LLM needed here — keywords are enough per the project plan.
"""

DEBUG_KEYWORDS = {
    "error", "fail", "crash", "log", "debug",
    "timeout", "exception", "issue", "problem",
    "traceback", "wrong", "not working", "failed",
    "why", "broken", "investigate", "diagnose"
}


def route(query: str) -> str:
    """
    Return 'debugger' if the query contains debug keywords,
    otherwise return 'generic'.
    """
    query_lower = query.lower()
    for keyword in DEBUG_KEYWORDS:
        if keyword in query_lower:
            return "debugger"
    return "generic"