"""
Generate synthetic incident corpus for testing and evaluation.

This script uses Google Gemini to generate realistic postmortems, alerts,
Slack threads, and runbooks based on common SRE failure patterns.
"""
import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import random
import google.generativeai as genai

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel(settings.GEMINI_FLASH_MODEL)

# Services and failure patterns
SERVICES = [
    "auth-service",
    "payment-service",
    "cart-service",
    "search-service",
    "notification-service",
    "api-gateway",
    "database",
    "cache"
]

FAILURE_PATTERNS = [
    "connection pool exhaustion",
    "memory leak",
    "certificate expiration",
    "DNS failure",
    "deployment rollback needed",
    "database migration issue",
    "rate limiting misconfiguration",
    "cache stampede",
    "OOM (out of memory)",
    "disk space exhaustion",
    "network partition",
    "cascading failure",
]

SEVERITIES = ["P0", "P1", "P2", "P3"]
TEAMS = ["Platform", "Payments", "Commerce", "Infrastructure", "Security", "Data"]


async def generate_postmortem(service: str, failure_pattern: str, severity: str, date: datetime) -> str:
    """Generate a realistic postmortem document."""
    
    prompt = f"""Generate a realistic incident postmortem in Markdown format for the following incident:

Service: {service}
Failure Pattern: {failure_pattern}
Severity: {severity}
Date: {date.strftime('%Y-%m-%d')}

The postmortem should include:
1. YAML frontmatter with: title, date, severity, services (list), team
2. ## Summary section (2-3 sentences)
3. ## Timeline section (5-8 timestamped events)
4. ## Root Cause section (detailed explanation)
5. ## Resolution section (how it was fixed)
6. ## Action Items section (3-5 follow-up tasks)

Make it realistic with specific technical details, error codes, metrics, and timestamps.
Use realistic service interactions and infrastructure components."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating postmortem: {e}")
        return f"""---
title: {service.title()} {failure_pattern.title()}
date: {date.strftime('%Y-%m-%d')}
severity: {severity}
services: [{service}]
team: {random.choice(TEAMS)}
---

## Summary
On {date.strftime('%Y-%m-%d')}, the {service} experienced {failure_pattern}...

## Timeline
- {date.strftime('%H:%M')} UTC: Issue detected

## Root Cause
{failure_pattern} in {service}

## Resolution
Issue was resolved by restarting services.

## Action Items
- Monitor metrics
"""


async def generate_alert_payload(service: str, failure_pattern: str, severity: str, date: datetime) -> Dict[str, Any]:
    """Generate a PagerDuty-style alert payload."""
    
    return {
        "id": f"alert-{random.randint(1000, 9999)}",
        "type": "incident",
        "summary": f"{service}: {failure_pattern}",
        "severity": severity.lower(),
        "status": "triggered",
        "service": {
            "name": service,
            "id": f"svc-{service}"
        },
        "created_at": date.isoformat(),
        "urgency": "high" if severity in ["P0", "P1"] else "low",
        "description": f"Alert: {service} is experiencing {failure_pattern}. "
                      f"Multiple instances affected. Response time degraded.",
        "escalation_policy": "default-escalation",
        "assigned_to": random.choice(["on-call-engineer", "sre-team", "dev-team"]),
        "incident_key": f"inc-{date.strftime('%Y%m%d')}-{random.randint(100, 999)}"
    }


async def generate_slack_thread(service: str, failure_pattern: str, date: datetime) -> List[Dict[str, Any]]:
    """Generate a Slack incident thread."""
    
    engineers = ["alice", "bob", "charlie", "dana", "eve"]
    base_time = date
    
    messages = [
        {
            "timestamp": base_time.isoformat(),
            "user": "alertbot",
            "text": f"🚨 INCIDENT: {service} - {failure_pattern} detected. P1 severity."
        },
        {
            "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "user": random.choice(engineers),
            "text": "I'm taking a look. Checking logs now."
        },
        {
            "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
            "user": random.choice(engineers),
            "text": f"Seeing elevated error rates in {service}. Investigating root cause."
        },
        {
            "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
            "user": random.choice(engineers),
            "text": f"Root cause identified: {failure_pattern}. Working on fix."
        },
        {
            "timestamp": (base_time + timedelta(minutes=20)).isoformat(),
            "user": random.choice(engineers),
            "text": "Fix deployed. Monitoring recovery."
        },
        {
            "timestamp": (base_time + timedelta(minutes=25)).isoformat(),
            "user": "alertbot",
            "text": "✅ RESOLVED: Metrics returning to normal."
        }
    ]
    
    return {
        "channel": f"#incident-{date.strftime('%Y%m%d')}",
        "thread_ts": base_time.isoformat(),
        "messages": messages
    }


async def generate_runbook(service: str, procedure: str) -> str:
    """Generate a runbook document."""
    
    prompt = f"""Generate a technical runbook in Markdown format for:

Service: {service}
Procedure: {procedure}

Include:
1. ## Overview (when to use this runbook)
2. ## Prerequisites (required access, tools)
3. ## Steps (detailed step-by-step instructions with commands)
4. ## Verification (how to verify success)
5. ## Rollback (if needed)

Make it actionable with specific commands, file paths, and verification steps."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating runbook: {e}")
        return f"""# {service.title()}: {procedure.title()}

## Overview
This runbook describes how to {procedure} for {service}.

## Steps
1. Check status
2. Execute procedure
3. Verify

## Verification
Check metrics dashboard."""


async def generate_corpus():
    """Generate complete synthetic corpus."""
    
    # Base paths
    base_path = Path("data/synthetic")
    postmortems_path = base_path / "postmortems"
    alerts_path = base_path / "alerts"
    slack_path = base_path / "slack_threads"
    runbooks_path = base_path / "runbooks"
    
    # Ensure directories exist
    for path in [postmortems_path, alerts_path, slack_path, runbooks_path]:
        path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting synthetic corpus generation...")
    
    # Generate 50 postmortems
    logger.info("Generating postmortems...")
    start_date = datetime(2024, 1, 1)
    
    for i in range(50):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        severity = random.choice(SEVERITIES)
        incident_date = start_date + timedelta(days=random.randint(0, 450))
        
        logger.info(f"Generating postmortem {i+1}/50: {service} - {failure}")
        
        content = await generate_postmortem(service, failure, severity, incident_date)
        
        filename = f"{incident_date.strftime('%Y-%m-%d')}-{service}-{failure.replace(' ', '-')}.md"
        filepath = postmortems_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Add small delay to avoid rate limits
        await asyncio.sleep(2)
    
    logger.info("✓ Generated 50 postmortems")
    
    # Generate 200 alert payloads
    logger.info("Generating alerts...")
    alerts = []
    
    for i in range(200):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        severity = random.choice(SEVERITIES)
        alert_date = start_date + timedelta(days=random.randint(0, 450), hours=random.randint(0, 23))
        
        alert = await generate_alert_payload(service, failure, severity, alert_date)
        alerts.append(alert)
    
    # Save alerts to individual JSON files
    for i, alert in enumerate(alerts):
        filepath = alerts_path / f"alert-{i+1:04d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(alert, f, indent=2)
    
    logger.info("✓ Generated 200 alerts")
    
    # Generate 30 Slack threads
    logger.info("Generating Slack threads...")
    
    for i in range(30):
        service = random.choice(SERVICES)
        failure = random.choice(FAILURE_PATTERNS)
        thread_date = start_date + timedelta(days=random.randint(0, 450))
        
        thread = await generate_slack_thread(service, failure, thread_date)
        
        filepath = slack_path / f"thread-{i+1:04d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(thread, f, indent=2)
    
    logger.info("✓ Generated 30 Slack threads")
    
    # Generate 20 runbooks
    logger.info("Generating runbooks...")
    procedures = [
        "restart service",
        "scale replicas",
        "clear cache",
        "rotate credentials",
        "failover to backup",
        "roll back deployment",
        "increase connection pool",
        "vacuum database",
        "check disk space",
        "restart worker processes"
    ]
    
    for i in range(20):
        service = random.choice(SERVICES)
        procedure = random.choice(procedures)
        
        logger.info(f"Generating runbook {i+1}/20: {service} - {procedure}")
        
        content = await generate_runbook(service, procedure)
        
        filename = f"{service}-{procedure.replace(' ', '-')}.md"
        filepath = runbooks_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        await asyncio.sleep(2)
    
    logger.info("✓ Generated 20 runbooks")
    
    logger.info("=" * 60)
    logger.info("CORPUS GENERATION COMPLETE!")
    logger.info(f"Postmortems: {len(list(postmortems_path.glob('*.md')))}")
    logger.info(f"Alerts: {len(list(alerts_path.glob('*.json')))}")
    logger.info(f"Slack threads: {len(list(slack_path.glob('*.json')))}")
    logger.info(f"Runbooks: {len(list(runbooks_path.glob('*.md')))}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(generate_corpus())
