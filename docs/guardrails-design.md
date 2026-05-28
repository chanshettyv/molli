

**Related files:** `shared/molli_shared/guardrails/base.py`, `docs/guardrail-eval-prompts.md`

## Overview

Each guardrail evaluates an incoming user message before it reaches the Gemini prompt chain. The `base.py` protocol defines four possible actions:

| Action | Meaning |
|--------|---------|
| `ALLOW` | Message is safe — pass to Gemini normally |
| `BLOCK` | Message is refused — return canned response, do not call Gemini |
| `ESCALATE` | Message requires human involvement — return canned response + notify designated contact |
| `REDACT` | Strip sensitive content before passing to Gemini (used for PII) |

Every guardrail trigger — regardless of action — must be **logged** with: timestamp, user ID (hashed), space ID, trigger category, matched pattern or signal, action taken, and canned response sent. No raw message content in logs beyond session.

---

## 1. Mental Health

### Trigger Conditions

Molli detects one or more of the following in a user message:

- **Explicit distress language:** "I want to hurt myself," "I can't go on," "I'm thinking about suicide," "I don't see the point anymore," "I want to die"
- **Implicit distress signals:** "I'm not okay," "everything feels hopeless," "I can't do this anymore," "no one would notice if I was gone"
- **Crisis terminology:** "overdose," "self-harm," "end it all," "harm myself," references to methods of suicide or self-harm in a personal context
- **Workplace distress escalation:** repeated expressions of severe hopelessness, helplessness, or desperation within a single session

Detection should use keyword matching as a first pass and a Gemini classification call as a second pass for ambiguous cases. Do not rely on keyword matching alone — "I want to kill this bug" should not trigger.

### Action

`ESCALATE`

- Immediately return the canned response below
- Do **not** attempt to answer any other part of the message
- Log the interaction with category `MENTAL_HEALTH` and flag `escalated: true`
- ⚠️ **Do not** notify a manager automatically without Sally Sousa's explicit approval — this is a privacy-sensitive decision. Pending her input, log only.
- Do **not** create a Freshservice ticket for mental health triggers

### Canned Response

> I'm really glad you reached out, and I want to make sure you get the right support.
>
> Please connect with Preiss's Employee Assistance Program (EAP) — they offer free, confidential support 24/7:
>
> **EAP Contact:** [PENDING — Sally Sousa to confirm provider name, phone number, and any Preiss-specific instructions]
>
> If you're in immediate danger, please call or text **988** (Suicide & Crisis Lifeline) or go to your nearest emergency room.
>
> You don't have to navigate this alone. 💙

> ⚠️ **Note for implementation:** Do not hardcode this message until Sally confirms the EAP details. Use a Secret Manager value for the EAP contact block so it can be updated without a redeploy.

### What Gets Logged

- Trigger category: `MENTAL_HEALTH`
- Signal type: `explicit` | `implicit` | `crisis_term`
- Action: `ESCALATE`
- Canned response sent: `true`
- Raw message: **NOT logged** — flag only

---

## 2. Fair Housing Act (FHA)

### Trigger Conditions

Any message that asks Molli to provide information, guidance, or opinions related to:

- **Protected characteristics in a housing context:** race, color, national origin, religion, sex, familial status, disability
- **Tenant screening based on protected class:** "can we reject applicants who…", "what do we do if a tenant is…" followed by any protected characteristic
- **Discriminatory steering:** questions about which neighborhoods to recommend or avoid based on demographics
- **Occupancy standards with discriminatory intent:** "how many people can we allow in a unit" phrased in a way that targets families or national origin
- **Disability accommodation refusal guidance:** "do we have to let them have a service animal," "do we have to modify the unit"

Trigger on questions from **employees asking how to screen, reject, or treat tenants differently** based on protected class. Do not trigger on general Fair Housing educational questions (e.g., "what is the Fair Housing Act?") — those can be answered with factual information and a referral to HR.

### Action

`BLOCK`

- Return canned response below
- Do not pass the message to Gemini
- Log with category `FHA`
- If the same user triggers FHA more than twice in a 7-day window, escalate to Sally Sousa

### Canned Response

> I'm not able to help with that request.
>
> Preiss is committed to full compliance with the Fair Housing Act. Providing guidance on screening, rejecting, or treating applicants or tenants differently based on race, color, national origin, religion, sex, familial status, disability, or any other protected class isn't something I can assist with.
>
> If you have a specific situation you're navigating, please contact **HR (Sally Sousa)** or your regional compliance officer directly. They can give you guidance that's appropriate and legally sound.

### What Gets Logged

- Trigger category: `FHA`
- Protected class detected (if identifiable): e.g., `national_origin`, `disability`
- Action: `BLOCK`
- Repeat trigger flag: `true/false`
- User ID: hashed

---

## 3. FCRA (Fair Credit Reporting Act)

### Trigger Conditions

Any message related to:

- **Background check guidance:** "how do I run a background check," "what shows up on a background check," "can we check their criminal history"
- **Credit report discussion:** "can we pull their credit," "what credit score do we require," "how do I read a credit report"
- **Adverse action language:** "how do I tell someone they were rejected because of their background check," "adverse action notice," "denial based on credit"
- **Consumer report interpretation:** asking Molli to interpret or summarize the contents of a specific applicant's background or credit report
- **Screening criteria that implicates FCRA:** "can we automatically reject anyone with a felony," "what's our policy on evictions on a record"

Coordinate with Sally Sousa and Lane Sheer on the tenant screening rules specifically — this is flagged as the highest real-world FCRA/FHA risk surface in the ticket audit.

Do **not** trigger on HR employees with verified authorization asking about internal background check process documentation (a future role-based access feature — stub for now, treat all users as unauthorized).

### Action

`BLOCK`

- Return canned response below
- Do not pass to Gemini
- Log with category `FCRA`
- All FCRA triggers are flagged for Sally Sousa's weekly review

### Canned Response

> I'm not able to provide guidance on background checks, credit reports, or adverse action under the Fair Credit Reporting Act.
>
> This area requires verified HR authorization and legal review. Please contact **HR (Sally Sousa)** directly for any screening-related questions.
>
> Handling this incorrectly can create legal exposure for Preiss — please don't rely on informal guidance for FCRA matters.

### What Gets Logged

- Trigger category: `FCRA`
- Subcategory: `background_check` | `credit_report` | `adverse_action` | `screening_criteria`
- Action: `BLOCK`
- Flagged for Sally weekly review: `true`

---

## 4. OSHA / Workplace Safety

### Trigger Conditions

Two tiers:

**Tier 1 — Immediate/Active Safety Emergency (ESCALATE):**
- "there's a fire," "someone is injured," "there's been an accident," "gas leak," "someone collapsed," "there's a fight," "active threat," "emergency"
- Any message describing an ongoing safety incident in present tense

**Tier 2 — Safety Question or Concern (ALLOW with caveats):**
- General OSHA compliance questions: "what's the OSHA requirement for X," "are we required to post safety notices"
- Incident reporting questions: "how do I report an injury," "what's the process after a workplace accident"
- These can be answered from Document360 with a strong referral to the Operations safety officer

Tier 1 takes priority. If both signals are present, treat as Tier 1.

### Action

**Tier 1:** `ESCALATE`  
**Tier 2:** `ALLOW` (with mandatory referral appended to the Gemini response)

### Canned Response — Tier 1 (Emergency)

> **This sounds like an active safety situation — please stop and act immediately:**
>
> 1. **Call 911** if there is any immediate risk to life
> 2. **Evacuate** the area if needed and follow your site's emergency plan
> 3. **Notify your site manager or Operations lead immediately** — do not wait
>
> Once everyone is safe, report the incident through Freshservice or contact the Preiss Operations safety officer.
>
> I'm logging this interaction now so the safety team is aware.

### Mandatory Referral Appended to Tier 2 Answers

> ⚠️ For any active safety concern or incident, stop using Molli and contact your site manager or the Operations safety officer directly. I can answer general questions, but I'm not a substitute for real-time safety judgment.

### What Gets Logged

- Trigger category: `OSHA`
- Tier: `1_emergency` | `2_question`
- Action: `ESCALATE` or `ALLOW`
- For Tier 1: Operations safety officer notification flag: `true` *(notification mechanism TBD with Adam/Lane)*

---

## 5. Escalation (3-Tier)

### Trigger Conditions

This guardrail governs the escalation flow across all categories, not just safety. It activates when:

- **Tier 1 → Tier 2 trigger:** Gemini confidence score is `low` OR Gemini explicitly states it doesn't know → offer Freshservice ticket
- **Tier 2 → Tier 3 trigger (human handoff):** any of the following:
  - A Mental Health, FHA, or FCRA guardrail fires
  - A Tier 1 OSHA emergency fires
  - User explicitly asks to "speak to a person," "talk to someone," "escalate this," "get a human"
  - User has rejected the Freshservice ticket offer and re-asks the same question twice
  - Ticket has been open > 24 hours with no response (future automation — stub for now)

### Action

| Tier | Trigger | Action |
|------|---------|--------|
| 1 | Molli answers from D360 | `ALLOW` |
| 2 | Low confidence / unknown | Offer Freshservice ticket (confirmation card) |
| 3 | Sensitive / unresolvable / explicit request | `ESCALATE` — human handoff with full conversation log |

### Canned Responses

**Tier 2 — Ticket Offer:**
> I wasn't able to find a confident answer to that in Preiss Central. I can open a support ticket so the right team can follow up with you directly.
>
> Here's what I'd include:
> **Subject:** [auto-generated from question]
> **Description:** [conversation summary]
> **Priority:** Normal
>
> [**Confirm**] [**Edit details**] [**No thanks**]

**Tier 3 — Human Handoff:**
> This one needs a human. I'm connecting you with the right person at Preiss and sending them the full context of our conversation so you don't have to repeat yourself.
>
> Someone will follow up with you shortly. If it's urgent, please reach out directly to your manager or the relevant department lead.

### What Gets Logged

- Escalation tier reached: `1` | `2` | `3`
- Reason: `low_confidence` | `guardrail_fire` | `user_requested` | `repeat_question`
- Ticket created: `true/false` + ticket ID if created
- Conversation log attached: `true/false`

---

## 6. Data Privacy

### Trigger Conditions

Two modes:

**Mode A — Input scanning (pre-Gemini, via Cloud DLP):**
Scan every user message before it reaches Gemini for:
- Social Security Numbers (SSN)
- Credit card numbers
- Bank account numbers
- Driver's license numbers
- Passport numbers
- Full date of birth combined with full name
- Medical record numbers

**Mode B — Output scanning (post-Gemini, before sending to user):**
Scan Gemini's response for any of the above — catches cases where D360 content accidentally contains PII.

### Action

**Mode A:** `REDACT` — strip the PII from the message, pass the redacted version to Gemini, log the redaction  
**Mode B:** `REDACT` — strip PII from response before sending to user, log the redaction  

If the entire message is PII (e.g., user pastes a full SSN with no question), `BLOCK` instead.

### Canned Response — Redaction Notice (shown to user)

> Just a heads up — I noticed your message contained what looks like sensitive personal information (like a Social Security Number or account number). I've removed it before processing your question to keep your data safe.
>
> For anything involving personal data or account details, please contact HR or IT directly rather than sharing it here.

### Canned Response — Full Block

> I can't process that message because it appears to contain sensitive personal information. Please don't share SSNs, account numbers, or other personal data in chat.
>
> If you need help with something involving personal data, contact HR (Sally Sousa) or IT (Adam Tomlinson) directly.

### What Gets Logged

- Trigger category: `DATA_PRIVACY`
- Mode: `input_scan` | `output_scan`
- PII type detected: e.g., `SSN`, `credit_card` (type only — never log the value)
- Action: `REDACT` | `BLOCK`
- Raw content: **NEVER logged**

---

## Implementation Notes

- All canned response strings should live in a config file or Secret Manager value — not hardcoded — so they can be updated without a redeploy
- Guardrails run **before** Gemini in the request pipeline, except Data Privacy Mode B which runs after
- Mental Health EAP contact block is **pending Sally Sousa review** — do not ship without it
- OSHA Tier 1 Operations safety officer notification mechanism needs to be confirmed with Adam Tomlinson and Lane Sheer
- FHA/FCRA repeat-trigger escalation to Sally requires her email to be stored in Secret Manager as `hr-escalation-email`
