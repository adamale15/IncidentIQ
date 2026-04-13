---
title: Cart Service - Certificate Expiration
date: 2024-07-20
severity: P2
services: [cart-service]
team: Payments
---

## Summary
On 2024-07-20, the cart-service experienced certificate expiration leading to service degradation.

## Timeline
- 00:00 UTC: Alert triggered for elevated error rates
- 00:05 UTC: On-call engineer acknowledged
- 00:15 UTC: Root cause identified
- 00:30 UTC: Fix deployed and verified

## Root Cause
The cart-service was experiencing certificate expiration due to misconfiguration in the deployment.

## Resolution
Issue was resolved by rolling back the recent deployment and applying the correct configuration.

## Action Items
- Add monitoring for this failure pattern
- Update runbooks with recovery procedures
- Review deployment checklist
