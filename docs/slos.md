# SLO contract and error-budget math

The example customer operation is `GET /api/work`. We measure completed server-side requests. The API has no real downstream database; its child span models a dependency.

## Definitions

Let `N` be eligible completed 2xx or 5xx requests, `E` the 5xx subset, and `F` the subset completing within 0.3 seconds.

- Availability SLI: `1 - E / N`; objective `0.999`; bad fraction `E / N`.
- Latency SLI: `F / N`; objective `0.99`; bad fraction `1 - F / N`.
- Burn rate: `bad fraction / (1 - objective)`.
- Budget remaining: `1 - bad fraction / (1 - objective)` over the reporting period. Negative means overspent.

For example, 100,000 eligible requests allow 100 unavailable requests and 1,000 slow requests in their respective budgets. A 1% availability error rate burns a 0.1% budget at 10×. Availability is request-based; a time-based downtime allowance is not interchangeable when traffic varies.

The latency histogram explicitly includes the 0.3-second bucket. We sum bucket and count rates across pods before dividing. We do not average pod percentages or use p95 as an SLI. The dashboard p95 is diagnostic only.

## Population and limitations

The route and method labels are fixed; status values are bounded. We never use raw paths, request IDs, user IDs, or trace IDs as metric labels. Trace IDs appear only in exemplars and logs.

Probes and `/metrics` are excluded. Invalid demo headers produce 400 and are excluded from both denominators. Other paths do not enter this API SLI. A fast failure may meet latency while violating availability; a slow failure violates both. Combine the predicates if your product requires a single successful-and-fast objective.

No traffic produces `0/0`, hence NaN. Empty telemetry remains absent. Neither is coerced into a healthy SLI. Separate alerts identify no traffic and missing scrape targets. All targets down and no targets discovered both trigger `SreApiUnavailable`; one healthy replica prevents this total-outage alert. A partial replica failure needs a separate redundancy alert if your operational policy requires one.

Request rates use counter-reset-aware `rate()` before aggregation. The 30-day report uses `increase()` before aggregation. A new process initializes 200/400/503 label sets, so zero-error traffic does not leave the error numerator absent. Prometheus cannot recover events before its first scrape, after a crash before scraping, or from requests that never reach the application.

## Alert policy

Two windows must simultaneously breach the same threshold. A high long-window value with a healthy short window indicates recovery and does not keep the burn alert active. Tests explicitly cover that behavior, healthy traffic, a short spike, sustained faults, missing targets, and zero denominators.

For 30 days = 720 hours, budget fraction consumed is approximately:

`burn rate × window hours / 720`

Thus 14.4× for one hour ≈ 2%; 6× for six hours = 5%. This interpretation assumes roughly constant request volume. The additional `for` durations trade slower detection for fewer noisy pages. `critical` and `warning` are lab routing severities; the warning is inhibited when the same service and SLO has a critical alert.

There is deliberately no minimum-volume gate. Low-volume services can page on a few failures; document a product-specific policy and add synthetic probes or a volume gate if appropriate. A missing full history window does not prevent Prometheus from evaluating against the history available. Warm up the lab before comparing alert timing to a mature production service.

## Production extension

Use a reviewed SLO contract with product owners. Add ingress/client SLIs, black-box reachability, durable storage, paging integrations, and an explicit budget policy for releases. Validate alert routing with a synthetic notification before depending on it for an incident. This repository does not send external notifications.
