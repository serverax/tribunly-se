# Price Decision Required

Repo scan:

```text
backend/api/main.py:1015:                "Claim appears viable. Unlock tribunal-ready documents for £29.99"
backend/api/main.py:1032:                    "payment_amount_gbp": 29.99 if viable else 0,
backend/api/main.py:1058:            next_step = f"Claim appears viable. Unlock tribunal-ready documents for £29.99"
backend/api/main.py:1075:                "payment_amount_gbp": 29.99 if viable else 0,
backend/api/payment_routes.py:85:        "full_documents": 2999,  # £29.99
backend/tests/test_payment_integration.py:102:    assert response.amount_pence == 2999  # £29.99
client/public/index.html:282:        <div class="price-tag">£29.99 <small>one-off</small></div>
client/public/pages/assessment.html:775:    payBtn.textContent = 'Unlock Full Documents (£29.99)';
client/public/pages/assessment.html:1138:            stripePayBtn.textContent = 'Unlock Full Documents (£29.99)';
```

Current repo position:

- Repo-coded price: `£29.99`
- Owner decision on record: `£99`
- No code changes made in this order

Files likely touched if the owner changes the decision:

- `backend/api/main.py`
- `backend/api/payment_routes.py`
- `backend/tests/test_payment_integration.py`
- `client/public/index.html`
- `client/public/pages/assessment.html`

Open item:

- Keep the pricing decision owner-gated. This note only records the discrepancy and the affected surfaces.
