"""lawapp 4-agent architecture (AEE / ART / SEA / Citation Guard).

Agents are stateless processors called only by the Mother Algorithm (brain.py).
They never call each other, never write the DB directly, and every output is
validated against the strict Pydantic schemas in ``schemas.py`` before use.
"""
