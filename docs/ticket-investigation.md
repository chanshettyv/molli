# Ticket investigation

Goal: audit the top recurring tickets in each department to define Molli's knowledge priorities. Findings feed Phase 1 (which articles to seed in the index) and Phase 2 (which guardrails to test against real cases).

**Data:** 90-day Freshservice exports — 890 Operations tickets, 510 IT tickets, 300 HR tickets (1,700 total).

## Method

For each department:

1. Pull the 90-day Freshservice ticket export filtered to that category.
2. Cluster tickets by `Issue` and `System` fields (much cleaner than subject-line clustering — these are Freshservice's own categorization). For HR, where these fields collapse to single values, cluster by subject pattern.
3. Interview the SME to validate clusters and surface tribal knowledge that isn't documented anywhere.
4. For each cluster, fill in the columns in the table below:
   - `molli_resolvable`: can Molli answer with Document360 content alone? Y / N / Partial
   - `exists_in_d360`: is there already an article that covers this? Y / N / Partial (Assumed N pending Aswin's confirmation — flagged as a follow-up.)
   - `guardrail_tag`: any of FCRA / FHA / OSHA / MH / none
   - `needs_approval_workflow`: does resolving this require an approval step we'd need to model in Phase 2? Y / N
5. Add notes on what content needs to be created or rewritten in D360.

## SME contacts (slide 12)

| Department | SME | Notes |
|---|---|---|
| Operations | Lane Sheer, Toni Yrlas | Policy and process documentation owners |
| HR | Sally Sousa | Compliance reviewer; escalation approver |
| IT | Adam Tomlinson | Freshservice admin; GCP support |
| Document360 | Aswin Ramesh (Kovai) | CC Lane, Toni, Whitney Kidd on ALL D360 comms |

## Assignment (today)

| Department | Owner |
|---|---|
| Operations | Kautilya |
| Human Resources | Sidney |
| Information Technology | Vedant |

## Findings — Operations

_Analyzed by Kautilya. 890 tickets, 90 days._

Top-level pattern: **57% of all Ops tickets target a single system, Entrata** (the property management platform). Most tickets are not "how do I do X?" questions — they're requests for an admin to perform an action inside Entrata that the requester either can't do themselves (permission-gated) or hasn't been trained to do. This significantly limits Molli's deflection potential: Molli can explain *how* to do something, but can't actually grant Entrata permissions or post charges on someone's behalf.

| Rank | Cluster label | Example subject | Volume (90d) | molli_resolvable | exists_in_d360 | guardrail_tag | needs_approval | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Entrata "Something Else" (catch-all) | "Move in date" / "Legal Inquiry" / "Update to Premium" | 118 | Partial | N | none | Y | Catch-all bucket. Heterogeneous — some are how-to questions Molli could answer, many require admin action. Worth a follow-up with Lane to break this category up in Freshservice's intake form. |
| 2 | User Access & Permissions (Entrata) | "Request access for Seth Hooper to add charges in Entrata" | 116 | N | N | none | Y | Provisioning request, not a question. Molli can't grant access; should route directly to ticket creation with structured fields (who, which property, what permissions). |
| 3 | Ledgers — payments, charges, credits | "Refund payment from March 1st - Emery Langston" / "Scheduled charges keep expiring" | 69 | Partial | N | none | Y | Two flavors: (a) "do this for me" refund/reversal requests — not Molli-resolvable; (b) "why is this happening?" troubleshooting (e.g., scheduled charges expiring) — Molli could explain if D360 has the article. |
| 4 | Lease Docs & Fees | "Correcting address on Renewal lease" / "Switching guarantor mid-lease" | 54 | Partial | N | none | Partial | Procedural questions ("can I switch a guarantor mid-lease?") are Molli-resolvable if documented. Document errors ("address shows SC instead of FL") are not. |
| 5 | Import Charges (electric/utility) | "Electric Overages" / "Upload Utility Charges" | 40 | N | N | none | Y | Recurring monthly task asking an admin to post bulk charges. Not a knowledge question. Candidate for Phase 2 automation, not Molli deflection. |
| 6 | Screening Issues | "Screening Authorization Form Error" / "Error pop-up during Apply & Satisfy Conditions" | 36 | Partial | N | **FCRA / FHA risk** | Y | Mostly tech errors with Entrata's screening workflow. Sensitive topic: tenant screening is FCRA/FHA-adjacent. Molli should answer process questions but **refuse anything about screening criteria, applicant denial reasons, or adverse action language.** Sally should review Molli's responses here. |
| 7 | System Settings | "Add 6-month lease term for Vintages" / "Lead assignment update" | 29 | N | N | none | Y | Admin-only configuration changes. Not Molli-resolvable. |
| 8 | Resident Portal issues | "Resident can't access portal" / "Mastercard rejected" | 26 | Partial | N | none | Partial | Common how-to questions (how does a resident reset their portal password?) are Molli-resolvable. Payment errors needing investigation are not. |
| 9 | Travtus Chatbot issues | "Chatbot not responding" / "Wrong answer given by chatbot" | 24 | N | N | none | N | Reports about a *different* chatbot (Travtus, used for resident-facing chat). Meta — Molli answering "the other chatbot is broken" is uncomfortable. Route straight to ticket. |
| 10 | Update Office Hours | "Update office hours for Cabana Beach" | 13 | N | N | none | N | Standard request to push hours to property websites. Could be a Phase 2 self-service form, not Molli content. |

**% estimated resolvable by Molli:** ~10–15% of Ops tickets (mostly slices of clusters 1, 3, 4, and 8 — the procedural "how do I…" subset). Most Ops tickets are action requests that need an admin, not answerable questions.

**D360 articles to create or improve:**

- **Entrata: requesting access** — clear "self-service" doc explaining who to ask, what permissions exist, and what info to include in the request (will let Molli pre-fill a structured ticket vs. answer directly).
- **Entrata: refunds, reversals, and scheduled charges** — process doc covering the most common ledger questions; clarifies what residents vs staff can do.
- **Lease docs: guarantors, renewals, mid-lease changes** — procedural doc consolidating the patterns we see in cluster 4.
- **Resident portal troubleshooting** — covers password reset, payment method add, email-on-file updates.
- **Tenant screening process (FHA/FCRA-aware version)** — what staff *can* tell applicants, what they cannot. Co-write with Sally.

## Findings — Human Resources

_Analyzed by Sidney. 300 tickets, 90 days._

**Major finding: HR's "tickets" are almost entirely workflow notifications, not employee questions.** The Freshservice HR queue is being used as a routing/logging mechanism for HRIS (UltiPro) events. Of 300 tickets:

- 154 (51%) — **New Hire** workflow: forwarded onboarding forms (PAN/IT/Ops/Mktg request) and transfer request forms
- 120 (40%) — **Terminations**: automated "Termination Approved for [Name]" notifications from UltiPro
- 26 (9%) — **Change**: employee name changes, transfers, job title changes

These are not questions Molli can answer. They're system-to-system notifications and form forwards intended to trigger downstream provisioning (IT creates accounts, Ops adds property access, etc.). Molli has minimal direct deflection opportunity here, **but** the data points to a separate insight worth surfacing to Sally.

| Rank | Cluster label | Example subject | Volume (90d) | molli_resolvable | exists_in_d360 | guardrail_tag | needs_approval | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | UltiPro termination notifications | "UltiPro Notifications: Termination Approved for [Name]" | 102 | N | N | none | N | Automated workflow output, not a question. Not Molli-resolvable. May be a Phase 2 automation opportunity (auto-route to IT for offboarding). |
| 2 | New-hire PAN/IT/Ops/Mktg requests | "Fwd: EDIT: PAN/IT/Ops/Mktg Request: [Name] - [Role] at [Property]" | ~85 | N | N | none | N | Onboarding form forwards. Not a question. |
| 3 | Transfer requests | "Fwd: Transfer Request Form: [Name]" | 34 | N | N | none | N | Form forwards triggering property/role moves. Not Molli-resolvable. |
| 4 | Employee changes | "Employee Change: [Name]" / "Name Change Request Form" | 26 | N | N | none | N | Name/title updates. Not Molli-resolvable. |
| 5 | Onboarding-related questions (embedded in tickets) | varies; mined from descriptions | unclear | Partial | N | none | N | **Hypothesis:** real employee HR questions (benefits, PTO, leave, policy) exist in the workforce but **are not landing in this Freshservice queue.** They're going to Sally directly via email/Slack/Chat. Needs SME validation. |
| 6 | Benefits questions | not visible in this export | ? | Y (if asked) | N | none | N | Speculative — confirm with Sally that these happen and where they currently land. |
| 7 | PTO and leave policy questions | not visible in this export | ? | Y (if asked) | N | none | N | Same as above. |
| 8 | Onboarding "what do I do first?" questions | not visible in this export | ? | Y (if asked) | N | none | N | Same as above. |
| 9 | Policy questions (handbook, code of conduct) | not visible in this export | ? | Y (if asked) | **FCRA / FHA / MH** | N | If/when Molli surfaces these, this is the cluster Sally needs to review most closely for guardrails. |
| 10 | Distress / wellness signals in chat | (none found in this export, by design) | 0 | N (refuse + escalate) | N | **MH** | Y | Out of an abundance of caution: Molli must detect distress signals and escalate to EAP + Sally, even if zero such tickets appear in current data. Build the guardrail; test in QA. |

**% estimated resolvable by Molli (from this dataset):** ~0% — none of the visible HR ticket traffic is a knowledge question.

**Critical follow-up:** The 90-day Freshservice HR queue almost certainly does not represent the full universe of HR questions employees ask. **Real questions are going somewhere — email, Slack, hallway conversations.** Before drawing conclusions, Sidney to ask Sally:

1. Where do employees actually ask HR questions today? (probably email/Slack to Sally directly)
2. What are the top 10 most common questions she fields outside Freshservice?
3. Would she be willing to route a sample of those to Molli for a week to gather data?

Without that, Molli's HR coverage will look like a feature with no users.

**D360 articles to create or improve:**

- **Benefits overview** (medical, dental, vision, 401(k)) — entry-level reference employees can self-serve.
- **PTO and leave policy** — accrual rates, request process, what's paid vs unpaid.
- **Onboarding checklist** — first-week, first-30-days, first-90-days.
- **Code of conduct / employee handbook quick-reference** — searchable so Molli can cite specific policies.
- **Where to go for what** — directory mapping common HR needs (benefits, payroll, leave, compliance) to the right SME or system.

## Findings — Information Technology

_Analyzed by Vedant. 510 tickets, 90 days._

Of all three departments, **IT has the highest Molli-deflection potential** — many tickets are clear self-service questions ("how do I connect to the printer?") or admin requests that follow a fixed pattern (add user to distribution list X). Two-thirds of IT tickets are about Google Workspace (159) and Computer/Laptop issues (96).

| Rank | Cluster label | Example subject | Volume (90d) | molli_resolvable | exists_in_d360 | guardrail_tag | needs_approval | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | "Other" (heterogeneous catch-all) | "G drive" / "Want to install VLC" / "Wifi is down" | 94 | Partial | N | none | Partial | Mixed bag like Ops's "Something Else." Some are how-tos (~30%), others need a tech (~70%). Worth restructuring the intake form. |
| 2 | Add/remove user on email distribution list | "Please remove me from novaknoxville@preiss.com" / "Add Erin to Capex list" | 71 | Partial | N | none | Y | Molli can answer "how do I get added to X list?" but the actual add/remove is admin-only. Best fit: Molli collects the request (user, list, add/remove) and creates a structured ticket — no human triage needed. |
| 3 | Add/remove user (Google account) | "New hire account for [Name]" / "Disable [Name]" | 44 | N | N | none | Y | Provisioning. Tightly coupled to HR's new-hire/termination workflow. Phase 2: chain HR notification → auto-create IT provisioning ticket. |
| 4 | User account issues (Google) | "Lindsey can't log in" / "Email not loading" | 35 | Partial | N | none | Partial | "Locked out / can't log in" is a real opportunity — Molli explains the self-recovery flow before suggesting a ticket. |
| 5 | **Password resets (Google)** | "Reset Lindsey Bowman's Gmail password" | 29 | Y | N | none | Y | **Highest-deflection IT cluster.** Molli should explain the self-service reset, link to Google's recovery flow, and only create a ticket if the user has no recovery email/phone. Approval needed if a manager is requesting reset for a direct report. |
| 6 | Quote for new/replacement computer | "Need a laptop for new hire at The Forum" | 20 | Partial | N | none | Y | Procurement request. Molli can collect required fields (who, role, property, urgency) but Adam approves all hardware spend — keep human in the loop. |
| 7 | Printer connection issues | "Need to add new printer" / "Computer not finding printer" | 17 | Y | N | none | N | Classic how-to. Molli should have a clear step-by-step in D360. |
| 8 | User access in Entrata (cross-listed with Ops) | "Add Corp Accounting Printer Access" | 14 | N | N | none | Y | Cross-departmental. These also appear in Ops cluster 2 — coordinate. |
| 9 | Email delivery issues / Mimecast | "Not receiving emails from X" / "Mimecast holding messages" | 20 (combined) | Partial | N | none | N | Some are user-side fixes (check spam, release from Mimecast); some need IT to whitelist a sender. Molli can guide the first set. |
| 10 | Office hours updates (property websites) | "Update office hours for Cabana Beach" | 10 | N | N | none | N | Could be a self-service form; not really Molli content. |

**% estimated resolvable by Molli:** ~35–40% of IT tickets, concentrated in: password resets (29), printer connections (17), part of "Other" (~30), and the procedural portion of user-account issues (~15) and email/Mimecast (~10). High-value targets because they're high-volume *and* well-suited to a knowledge-base answer.

**D360 articles to create or improve:**

- **Google password reset and account recovery** — the single highest-impact article. Covers self-service first, escalation last.
- **Connecting to office printers** — step-by-step per OS (Windows/Mac), how to find the printer name, what to do when it doesn't appear.
- **Email delivery troubleshooting** — Mimecast release, sender whitelisting, spam folder checks.
- **Hardware request process** — what to include when asking for a new laptop, phone, or peripheral.
- **Distribution list self-service guide** — what lists exist per property, how to request add/remove.
- **VPN, Wi-Fi, and remote access** — currently scattered across tickets; consolidate.

## Cross-department synthesis

**Highest-volume clusters across all departments:**

1. Entrata "Something Else" catch-all (Ops, 118) — needs intake form restructuring more than D360 content
2. Entrata access/permissions requests (Ops, 116) — admin-gated, low Molli deflection
3. UltiPro termination notifications (HR, 102) — automated workflow, not a question
4. IT "Other" catch-all (94)
5. New-hire onboarding form forwards (HR, 85)
6. Entrata ledger requests — refunds, payments, credits (Ops, 69)
7. Email distribution list add/remove (IT, 71)
8. Entrata lease document errors and procedure questions (Ops, 54)
9. Google account add/remove (IT, 44)
10. Entrata import charges — monthly utility uploads (Ops, 40)

**Clusters that touch a guardrail (FCRA, FHA, OSHA, MH):**

A strict-keyword scan of all 1,700 tickets found **zero unambiguous guardrail-triggering tickets in the 90-day data.** Earlier broad-pattern searches surfaced 100+ "matches" that were all false positives — "race" matching "Grace Hill," "EAP" matching "Leap" (a payment system), "accident" matching "accidentally."

This means **guardrails cannot be validated against historical traffic.** Two implications:

1. **Build the guardrails defensively, not reactively.** They exist to handle worst-case messages that aren't in the corpus. Sidney's QA plan should use *synthetic* prompts (constructed examples, red-team exercises) rather than real ticket data.
2. **The one real cluster to flag is Ops's Screening Issues (36 tickets).** Tenant screening is the most realistic FCRA/FHA risk surface in this business. Molli must refuse to advise on screening criteria, denial reasons, or adverse action language. Co-write the relevant D360 article and the guardrail rules with Sally.

Edge cases worth manual review (low volume, sensitivity-adjacent):

- Ops evictions and legal inquiries (11 tickets) — auto-escalate, do not attempt to answer.
- IT correspondence with attorneys (7 tickets — quarantined emails, markup files) — handle normally; no guardrail trigger.

**Clusters that need approval workflows (Phase 2 candidates):**

- New-hire provisioning chain: HR onboarding form → IT account creation → Ops property access → Mktg listings. Currently three separate manual forwards (~130 tickets/quarter). Highest-ROI automation target.
- Offboarding chain: UltiPro termination → IT account disable → Ops access removal (~120 tickets/quarter).
- Entrata access provisioning (116 tickets) — structured ticket with manager approval gate.
- Hardware procurement (20 tickets) — Adam approves; Molli collects request fields.

**Overall estimated ticket deflection at launch:** **~15–18%** against the 20% YoY target.

Breakdown:

- **IT: ~35–40% of 510 tickets = ~180 deflected**
- **Ops: ~10–15% of 890 tickets = ~110 deflected**
- **HR: effectively 0% of the Freshservice queue is deflectable, but probably ~50% of the (currently invisible) email/Slack traffic could be — pending Sidney's follow-up with Sally to size that real demand**

Against 1,700 baseline tickets: ~290 deflected = ~17%. With the addition of HR's hidden demand once routed into Molli, hitting the 20% target is realistic but not guaranteed.

**Other findings worth flagging at the next team review:**

1. **Entrata is the center of gravity.** 57% of Ops, plus cross-listed IT tickets. Whoever owns the Document360 content map should make sure Entrata is documented thoroughly and tagged so Molli's retrieval surfaces it cleanly.
2. **Freshservice's intake form is too coarse.** The "Other" and "Something Else" buckets together hold 212 tickets (12% of the corpus). Even a small improvement in intake categorization would help Molli route better. Worth a conversation with Adam about whether the form can be revised in parallel.
3. **HR's deflection story is invisible in the current data.** Without a separate signal source (email/Slack/Sally directly), HR coverage will look unused at launch. Highest-priority follow-up for the Sidney → Sally conversation this week.
4. **The Travtus chatbot exists.** 24 Ops tickets reference issues with a different chatbot. Worth understanding what it does, where it lives, and whether there's overlap or risk of confusion with Molli. Lane or Toni would know.
