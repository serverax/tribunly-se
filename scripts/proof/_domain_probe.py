from backend.domains.registry import DomainDisabledError, enabled_domains, require_domain

print("enabled", enabled_domains())
require_domain("employment")
print("employment PASS")
try:
    require_domain("housing")
    print("housing UNEXPECTED")
except DomainDisabledError:
    print("housing DomainDisabledError")
try:
    require_domain("employment_uk")
    print("employment_uk UNEXPECTED")
except Exception as exc:
    print("employment_uk", type(exc).__name__)
