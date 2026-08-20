# Launch Postmortem — <PRODUCT> v<VERSION>

> For gate **G12.11**. Write it within a week, while it is still accurate.
>
> **Blameless.** The output is a process change, never a person's name. A postmortem that assigns
> fault teaches everyone to report less next time, which is precisely the opposite of the goal.

---

## Summary

| | |
|---|---|
| Launched | ___ |
| Reached 100% | ___ |
| Total rollout duration | ___ |
| Rollbacks | ___ |
| Incidents (S0 / S1 / S2) | ___ / ___ / ___ |
| Users affected by any incident | ___ |
| Success metric: target vs actual | ___ vs ___ |
| Readiness verdict at launch | GO / GO WITH CONDITIONS / NO-GO-overridden |

**In three sentences, what happened:**
> ___

---

## 1. What we predicted correctly

Risks identified before launch that turned out to be real. **This section justifies the cost of the
whole process** — it is the evidence that the gates earn their time.

| Predicted in | What we expected | What actually happened | Did the mitigation work? |
|---|---|---|---|
| | | | |

---

## 2. What surprised us

Everything that was not on the list.

| # | Surprise | Impact | Why we did not anticipate it |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

---

## 3. Which gate caught it

Every real problem found **before** launch, and the check that found it. This tells you which parts
of the process are paying for themselves — and which never find anything and could be trimmed.

| Problem found | Gate / check | Severity | Cost if it had shipped |
|---|---|---|---|
| | | | |

**Gates that found nothing this time:** ___
*(Not necessarily waste — some gates are insurance. But if a gate has found nothing across several
launches, ask whether it is checking the right thing for this product.)*

---

## 4. Which gate should have caught it

Every problem found **after** launch, and the check that missed it. **The most valuable section in
this document.**

| Problem | Which check should have caught it | Why it did not | Fix to the check |
|---|---|---|---|
| | | | |

For each row, the "why it did not" is one of:
- The check does not exist → **add it** (this is a G12.12 candidate)
- The check exists but was skipped → why? Time? Not applicable-by-mistake?
- The check exists and was run but was too weak → **rewrite it**
- The check ran against the wrong thing → wrong environment, wrong scale, wrong commit

---

## 5. Incident log

| # | Sev | Started | **Detected** | Mitigated | Resolved | Detected by | Root cause |
|---|---|---|---|---|---|---|---|
| | | | | | | monitor / customer / us | |

**How many were found by a customer before a monitor?** ___

*If that number is above zero, G10.05 has a gap, and closing it is probably the single most
valuable thing to come out of this launch.*

**Mean time to detect:** ___
**Mean time to mitigate:** ___

---

## 6. What users actually said

From G12.09. Real quotes and counts, not summaries.

| Theme | Count | Example quote | Disposition |
|---|---|---|---|
| | | "___" | fix now / next release / document |

**The thing users were most confused by:** ___

*Confusion is a defect. Ten people asking the same question is one design problem with ten reports,
and you can only collect this data in the first week.*

---

## 7. Timeline

| Time | Event |
|---|---|
| | Baseline captured |
| | Stage 1 deployed |
| | Stage 2 promoted |
| | ... |
| | 100% |
| | First incident |
| | T+72h, watch closed |

---

## 8. What we would do differently

Free text. Be specific. "Communicate better" is not an action; "post the staging URL in the support
channel two days before launch" is.

> ___

---

## 9. The one change

**G12.12 permits exactly one.** A postmortem that generates fifteen action items generates zero.

> **Change:** ___
>
> **Where it is written:** ___ (`references/gate-G__.md`, `scripts/catalog.py`, or the project's docs)
>
> **Made by:** ___ on ___
>
> **Why this one and not the others:** ___

- [ ] The change is actually made. Not filed. Made.

---

## 10. Items deliberately not acted on

Everything else worth noting that is **not** the one change. Writing them down means they are not
lost, and honestly labelling them as not-being-done-now is better than a backlog everybody ignores.

| Item | Why not now | Revisit when |
|---|---|---|
| | | |

---

## Appendix

| | |
|---|---|
| Evidence bundle | `launch-evidence-___.zip` |
| Report | `.launch/report/LAUNCH-REPORT.html` |
| Certificate | `.launch/CERTIFICATE.md` |
| Runbook used | ___ |
| Go/No-Go record | ___ |
