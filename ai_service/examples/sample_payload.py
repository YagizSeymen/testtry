"""Reusable sample payloads for local AI service testing."""

DEAL = {
    "deal_id": "deal_sample",
    "status": "draft",
    "intake": {
        "company_name": "Acme AI",
        "company_url": "https://example.com",
        "short_description": "AI workflow platform for finance teams.",
        "founder_names": ["Jane Founder", "Ali Builder"],
        "deck_text": None,
        "submitted_by": "demo",
    },
    "created_at": "2026-07-18T00:00:00Z",
    "updated_at": "2026-07-18T00:00:00Z",
}

SOURCE = {
    "source_id": "src_sample",
    "url": "https://example.com/about",
    "title": "Acme AI About",
    "kind": "company_site",
    "fetched_at": "2026-07-18T00:00:00Z",
    "http_status": 200,
}

PAGE_TEXT = """
Acme AI is an AI workflow platform for finance teams.
The company launched in 2025 and serves pilot customers in mid-market accounting teams.
Jane Founder previously built finance automation software before starting Acme AI.
The product integrates with ERP systems and automates monthly close workflows.
Acme AI uses subscription pricing for finance teams.
The company raised a seed round from angel investors.
The market for finance automation is growing as companies adopt AI tools.
Key risks include security review, compliance requirements, and long enterprise sales cycles.
"""
