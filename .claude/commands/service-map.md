---
description: Produce/refresh the microservice service map — classify each service REAL+WIRED / STUB / DEAD with health evidence.
---

# /service-map

Map the distributed services.

## Steps
1. `microservices-integration-agent` enumerates `services/**`.
2. For each: endpoints, factory compliance, real core call vs static, health/ready.
3. Classify REAL+WIRED / REAL-not-wired / STUB / DEAD.
4. Capture HTTP 200 health proof (compose or in-cluster) per service.
5. Write `tasks/MICROSERVICE_SERVICE_MAP.md`.

## Output
Table: service → endpoints → wiring → classification → health evidence.
