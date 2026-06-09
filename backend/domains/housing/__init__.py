"""
backend.domains.housing — PLACEHOLDER (not enabled).

This package exists so the platform's modular structure is symmetric and a real
housing domain can be dropped in later. It is registered in
``backend.domains.registry`` with ``enabled=False`` and owns NO matter types, so
every domain/matter guard fails closed for housing today.

To enable a real housing domain (future work), a contributor must:

  1. Implement the domain modules used by the pipeline, mirroring
     ``backend.domains.employment``:
       - rules / qualifying logic         (e.g. deadline.py, assess_logic.py)
       - templates registry               (templates/__init__.py: TEMPLATES dict)
       - any checklists / compliance logic
  2. Ingest a CITED housing corpus + an effective-dated rules pack
     (CLAUDE.md §7: no placeholder/uncited legal rows).
  3. Add real architecture + grounding + citation tests.
  4. Flip the registry entry to enabled=True and populate matter_types,
     jurisdiction, rules_pack, retrieval_domain, and templates_module.

Until all of the above exist, this domain MUST remain disabled.
"""
