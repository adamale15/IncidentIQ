---
title: Payment Service - Rate Limiting Misconfiguration
date: 2024-06-26
severity: P1
services: [payment-service]
team: Infrastructure
---

## Summary
On 2024-06-26, the payment-service experienced rate limiting misconfiguration leading to service degradation.

## Timeline
- 00:00 UTC: Alert triggered for elevated error rates
- 00:05 UTC: On-call engineer acknowledged
- 00:15 UTC: Root cause identified
- 00:30 UTC: Fix deployed and verified

## Root Cause
The payment-service was experiencing rate limiting misconfiguration due to misconfiguration in the deployment.

## Resolution
Issue was resolved by rolling back the recent deployment and applying the correct configuration.

## Action Items
- Add monitoring for this failure pattern
- Update runbooks with recovery procedures
- Review deployment checklist
