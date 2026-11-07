# Incident review: <short description>

Status: draft · Owner: <name> · Date: <date> · Environment: local lab

## Impact

Affected operation, eligible request count, unavailable/slow request counts, observed duration, and budget consumed. Separate measured data from estimates.

## Timeline

| Timestamp and timezone | Event | Evidence |
| --- | --- | --- |
| | Experiment started | Command and fault parameters |
| | First symptom | Metric query or trace |
| | Alert fired | Alert name and labels |
| | Mitigation | Action taken |
| | Recovery confirmed | Healthy traffic and resolved alert |

## Cause and contributing factors

Describe the mechanism, why it affected the SLI, what telemetry established it, and what remains unknown. Focus on systems and decisions rather than blame.

## Detection and response

What made diagnosis quick or slow? Did both alert windows behave as expected? Were there false positives, telemetry gaps, or unnecessary steps?

## Follow-up actions

| Action | Owner | Due date | Verification |
| --- | --- | --- | --- |
| | | | |

## Evidence

Dashboard screenshots, exact PromQL, trace IDs, relevant sanitized log lines, and commit/version identifiers. Never include secrets or private customer information.
