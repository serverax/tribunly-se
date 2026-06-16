"""Perpetual Law Brain  -  verified legal-source ingestion pipeline.

Stages: fetch (whitelist) -> validate domain -> parse -> critic gate -> graph link
-> chunk -> embed -> audit -> refresh retrieval index.

Hard rule: only official, whitelisted legal sources may enter the lawapp legal
brain. No arbitrary internet crawl. No AI-generated legal authority. Every legal
row carries provenance; every edge carries a citation.
"""
