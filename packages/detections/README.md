# Detection as code

`rules.json` contains ten reviewed, deterministic definitions. The implementation is `apps/api/aegisgraph/detection.py`. Each rule declares an ID, kind, severity, description, threshold and time window. Changing thresholds changes evaluation; rule kinds map to explicit Python predicates, with no expression evaluation or arbitrary executable code.

Novel authentication is calculated from earlier successful canonical events, requiring three prior observations. It is not trusted solely from a producer's novelty flags. Sequence detections require the earlier event to precede the later event and match the principal and session. Internal enumeration counts actual distinct endpoints within five minutes and suppresses duplicate alerts within that window. Volume is at least 1,000 rows; generated normal queries are at most 90 rows. These are documented demo thresholds, not production-calibrated false-positive claims.

Repeated failures is implemented/tested but does not fire in the main scenario. Ten alerts are expected because unseen authentication fires for both unusual devices. Detection IDs and alert IDs are deterministic. Alerts retain explicit source event references.

Correlation is a separate module: three distinct rules, at least two rule families, same principal, and at most thirty minutes from the first alert. IP/device/session graph relationships provide additional observable context; they do not independently join different principals into a case. The high-severity flagship requires account and privilege families. There is no opaque risk score and no model-driven grouping.
