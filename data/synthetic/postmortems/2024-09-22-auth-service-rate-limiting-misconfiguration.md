---
title: Auth Service - Rate Limiting Misconfiguration
date: 2024-09-22
severity: P0
services: [auth-service]
team: Platform
---

## Summary
On 2024-09-22, the auth-service experienced rate limiting misconfiguration leading to service degradation.

## Timeline
- 00:00 UTC: Alert triggered for elevated error rates
- 00:05 UTC: On-call engineer acknowledged
- 00:15 UTC: Root cause identified
- 00:30 UTC: Fix deployed and verified

## Root Cause
The auth-service was experiencing rate limiting misconfiguration due to misconfiguration in the deployment.

## Resolution
Issue was resolved by rolling back the recent deployment and applying the correct configuration.

## Action Items
- Add monitoring for this failure pattern
- Update runbooks with recovery procedures
- Review deployment checklist
