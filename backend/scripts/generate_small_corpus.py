"""
Generate SMALL synthetic corpus for quick testing (avoids rate limits).
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
import random

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICES = ["auth-service", "payment-service", "cart-service", "search-service"]
FAILURE_PATTERNS = ["connection pool exhaustion", "memory leak", "certificate expiration", "rate limiting misconfiguration"]
SEVERITIES = ["P0", "P1", "P2"]
TEAMS = ["Platform", "Payments", "Infrastructure"]


async def generate_small_corpus():
    """Generate small corpus without LLM (static templates)."""
    
    base_path = Path("../data/synthetic")
    postmortems_path = base_path / "postmortems"
    alerts_path = base_path / "alerts"
    slack_path = base_path / "slack_threads"
    
    for path in [postmortems_path, alerts_path, slack_path]:
        path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Generating small static corpus...")
    start_date = datetime(2024, 1, 1)
    
    # Generate 10 postmortems (static templates)
    for i in range(10):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        severity = random.choice(SEVERITIES)
        incident_date = start_date + timedelta(days=random.randint(0, 300))
        
        content = f"""---
title: {service.title().replace('-', ' ')} - {failure.title()}
date: {incident_date.strftime('%Y-%m-%d')}
severity: {severity}
services: [{service}]
team: {random.choice(TEAMS)}
---

## Summary
On {incident_date.strftime('%Y-%m-%d')}, the {service} experienced {failure} leading to service degradation.

## Timeline
- {incident_date.strftime('%H:%M')} UTC: Alert triggered for elevated error rates
- {(incident_date + timedelta(minutes=5)).strftime('%H:%M')} UTC: On-call engineer acknowledged
- {(incident_date + timedelta(minutes=15)).strftime('%H:%M')} UTC: Root cause identified
- {(incident_date + timedelta(minutes=30)).strftime('%H:%M')} UTC: Fix deployed and verified

## Root Cause
The {service} was experiencing {failure} due to misconfiguration in the deployment.

## Resolution
Issue was resolved by rolling back the recent deployment and applying the correct configuration.

## Action Items
- Add monitoring for this failure pattern
- Update runbooks with recovery procedures
- Review deployment checklist
"""
        
        filename = f"{incident_date.strftime('%Y-%m-%d')}-{service}-{failure.replace(' ', '-')}.md"
        filepath = postmortems_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    logger.info(f"✓ Generated 10 postmortems")
    
    # Generate 20 alerts
    for i in range(20):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        severity = random.choice(SEVERITIES)
        alert_date = start_date + timedelta(days=random.randint(0, 300), hours=random.randint(0, 23))
        
        alert = {
            "id": f"alert-{i+1:04d}",
            "type": "incident",
            "summary": f"{service}: {failure}",
            "severity": severity.lower(),
            "status": "triggered",
            "service": {"name": service},
            "created_at": alert_date.isoformat(),
            "description": f"Alert: {service} is experiencing {failure}."
        }
        
        filepath = alerts_path / f"alert-{i+1:04d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(alert, f, indent=2)
    
    logger.info(f"✓ Generated 20 alerts")
    
    # Generate 5 Slack threads
    for i in range(5):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        thread_date = start_date + timedelta(days=random.randint(0, 300))
        
        thread = {
            "channel": f"#incident-{thread_date.strftime('%Y%m%d')}",
            "thread_ts": thread_date.isoformat(),
            "messages": [
                {"timestamp": thread_date.isoformat(), "user": "alertbot", "text": f"🚨 {service} - {failure}"},
                {"timestamp": (thread_date + timedelta(minutes=2)).isoformat(), "user": "alice", "text": "Investigating"},
                {"timestamp": (thread_date + timedelta(minutes=10)).isoformat(), "user": "bob", "text": "Root cause found. Deploying fix."},
                {"timestamp": (thread_date + timedelta(minutes=20)).isoformat(), "user": "alertbot", "text": "✅ RESOLVED"}
            ]
        }
        
        filepath = slack_path / f"thread-{i+1:04d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(thread, f, indent=2)
    
    logger.info(f"✓ Generated 5 Slack threads")
    logger.info("=" * 60)
    logger.info("SMALL CORPUS GENERATION COMPLETE!")
    logger.info(f"Postmortems: {len(list(postmortems_path.glob('*.md')))}")
    logger.info(f"Alerts: {len(list(alerts_path.glob('*.json')))}")
    logger.info(f"Slack threads: {len(list(slack_path.glob('*.json')))}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(generate_small_corpus())
