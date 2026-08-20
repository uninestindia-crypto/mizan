# Go / No-Go — <PRODUCT> v<VERSION>

> For gate **G11.13**. Hold this meeting even if the team is one person — saying the risks out loud,
> to another human, surfaces the objection somebody has been privately holding for a week.

---

## Meeting

| | |
|---|---|
| Date / time | ___ |
| Proposed launch window | ___ |
| Chair | ___ |
| Attendees | ___ |
| Certificate verdict | **GO / GO WITH CONDITIONS / NO-GO** |
| Report | `.launch/report/LAUNCH-REPORT.html` |
| Evidence bundle | `launch-evidence-___.zip` |

---

## 1. The numbers

| | |
|---|---|
| Checks applicable to this profile | ___ of 216 |
| Passed | ___ |
| Failed | ___ |
| Not tested | ___ |
| Waived | ___ |
| N/A | ___ |
| **Open S0 blockers** | **___** |
| Open S1 warnings | ___ |
| Proof: executed / attached / asserted | ___ / ___ / ___ |

---

## 2. Open blockers

**Any row here means the answer is No-Go** unless the owner explicitly overrides in section 7.

| ID | Check | Why it is still open | Decision |
|---|---|---|---|
| | | | |

---

## 3. Waivers being accepted today

Read each `--risk` line **out loud**. The named person confirms verbally.

| ID | Check | Risk being accepted | Accepted by | Expires |
|---|---|---|---|---|
| | | | | |

---

## 4. The three questions

Each answered with a specific fact, not a reassurance.

**1. What is most likely to go wrong?**
> ___

**2. How will we find out — and how fast?**
> ___ (from G10.06: median ___ seconds from condition to a human's phone)

**3. How do we undo it, and how long does that take?**
> ___ (from G11.07: rollback measured at ___ seconds, executed by ___)

---

## 5. Readiness by area

| Area | Ready? | Owner | Notes |
|---|---|---|---|
| Engineering (G1–G3) | | | |
| Security (G4) | | | |
| Data & migrations (G5) | | | |
| Performance (G6) | | | |
| Reliability (G7) | | | |
| UX & accessibility (G8) | | | |
| Legal & privacy (G9) | | | |
| Operations (G10) | | | |
| Release mechanics (G11) | | | |
| Support & comms | | | |

---

## 6. Launch plan confirmed

- [ ] Window: ___ — not Friday evening, not before a holiday, no dependency maintenance
- [ ] Staged rollout with numeric thresholds agreed (G11.09)
- [ ] Abort condition agreed and written in the runbook
- [ ] **Abort authority named:** ___ (can call it alone, without debate)
- [ ] On-call confirmed and awake: ___
- [ ] Baseline will be captured at ___ (within 15 min of the first stage)
- [ ] Comms drafted: user announcement, support brief, "investigating an issue" message
- [ ] Status page access verified
- [ ] Runbook cold-read by ___, who did not write it

---

## 7. Decision

**Verdict: ___**

| Role | Name | Decision | Signature / confirmation | Date |
|---|---|---|---|---|
| Engineering owner | | GO / NO-GO | | |
| Security | | GO / NO-GO | | |
| Operations / SRE | | GO / NO-GO | | |
| Support | | GO / NO-GO | | |
| **Product owner (final)** | | **GO / NO-GO** | | |

### If launching over an open blocker

The product owner writes, in their own words, one sentence per blocker:

> **Blocker ___:** I am accepting the risk that ___. If it happens, ___ will be woken, and the
> mitigation is ___.

> **Blocker ___:** ___

*This paragraph will be read back during the incident. Write it as though it will be.*

---

## 8. Next checkpoint

| | |
|---|---|
| Next review | ___ (T+1h / T+24h) |
| Who convenes it | ___ |
| What would trigger an emergency review before then | ___ |

---

## Notes / dissent

Record any objection raised, including ones that were overruled. **A dissent that turns out to be
right and was never written down is the most expensive kind.**

> ___
