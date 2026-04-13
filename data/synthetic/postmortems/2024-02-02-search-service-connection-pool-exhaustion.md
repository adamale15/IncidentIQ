---
title: Search Service - Connection Pool Exhaustion
date: 2024-02-02
severity: P2
services: [search-service]
team: Platform
---

## Summary
On 2024-02-02, the search-service experienced connection pool exhaustion leading to service degradation.

## Timeline
- 00:00 UTC: Alert triggered for elevated error rates
- 00:05 UTC: On-call engineer acknowledged
- 00:15 UTC: Root cause identified
- 00:30 UTC: Fix deployed and verified

## Root Cause
The search-service was experiencing connection pool exhaustion due to misconfiguration in the deployment.

## Resolution
Issue was resolved by rolling back the recent deployment and applying the correct configuration.

## Action Items
- Add monitoring for this failure pattern
- Update runbooks with recovery procedures
- Review deployment checklist
