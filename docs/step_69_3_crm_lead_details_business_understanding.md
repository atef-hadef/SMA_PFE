# Step 69.3 — CRM Lead Details: Business Understanding

## 1. Objective

Transform the CRM Lead Details page from a technical status display into a complete, business-friendly client file that allows a commercial user to immediately understand:

- What the client wrote in the original form
- What product or service the client is interested in
- What the AI understood from the message
- Why the AI assigned the current score
- What concrete action the sales user should take next
- Full contact and context information
- Recent interaction history

---

## 2. Initial Problem

The CRM Lead Details page displayed status, score, priority, owner, and next action — but the commercial user could not understand the business context behind those values.

**Root cause:** Four key business sections were missing from the UI:

1. **Demande du client** — the original client message and request context were never displayed in a dedicated card.
2. **Besoin détecté par l'IA** — `ai_summary`, `intention`, `urgency`, `sentiment` were available in the DB and API but only shown as small chips in the insight panel, without the full AI summary text.
3. **Justification du score** — the score was shown as a number but no explanation of contributing factors was provided.
4. **Action commerciale recommandée** — `recommended_action` and `next_action` were available but not presented in a clear, actionable card with qualification questions.

Additionally, the `LeadBusinessProfile` contact card was missing `created_at` and `last_contact_at` fields.

---

## 3. Fields Available in PostgreSQL / API

All required fields were already present in the database and exposed through the API. No schema migration was needed.

### `crm_leads` table columns used:

| Column | Type | Used in |
|---|---|---|
| `id` | String | Header, Traceability |
| `full_name` | String | Header |
| `company_name` | String | Header, Contact |
| `email` | String | Contact |
| `phone` | String | Contact |
| `source` | String | Client Request card, Contact |
| `status` | String | Header badge |
| `customer_status` | String | Header badge, Score card |
| `lead_score` | Integer | Header, Score card |
| `sentiment` | String | AI Understanding card, Score card |
| `urgency` | String | AI Understanding card, Score card |
| `intention` | String | AI Understanding card, Score card |
| `message` | Text | **Client Request card** (new) |
| `ai_summary` | Text | **AI Understanding card** (new) |
| `recommended_action` | Text | **Sales Action card** (new) |
| `next_action` | Text | Header, Sales Action card |
| `product_service` | String | Client Request card, Contact |
| `estimated_value` | Numeric | Client Request card, Header |
| `priority` | String | Header, Score card |
| `location` | String | Client Request card, Contact |
| `created_at` | DateTime | **Contact card** (added), Client Request card |
| `last_contact_at` | DateTime | **Contact card** (added) |
| `notes` | Text | Traceability panel |

### `crm_interactions` table:
All interaction fields were already exposed and displayed in the activity timeline.

---

## 4. Fields Added or Exposed

**No database migration was required.** All fields were already in PostgreSQL and the FastAPI `CrmLeadDetail` schema.

The only change was **displaying** fields that were already available but not shown in the UI:

- `message` → now shown in `LeadClientRequestCard`
- `ai_summary` → now shown in `LeadAIUnderstandingCard`
- `intention` → now shown in `LeadAIUnderstandingCard`
- `recommended_action` → now shown in `LeadSalesActionCard`
- `created_at` → now shown in `LeadBusinessProfile` contact card
- `last_contact_at` → now shown in `LeadBusinessProfile` contact card

---

## 5. UI Sections Added

### Section 2b — Demande du client (`LeadClientRequestCard`)
A new card showing:
- **Message original du client** — `lead.message` (full text, multiline)
- **Produit / service demandé** — `lead.product_service`
- **Source du lead** — `lead.source` (formatted via `getCrmSourceLabel`)
- **Localisation** — `lead.location`
- **Valeur estimée** — `lead.estimated_value` (formatted via `formatCrmCurrency`)
- **Date de réception** — `lead.created_at` (formatted via `formatCrmDate`)

All fields show "Non disponible" if null/empty. No fake data.

### Section 2b — Besoin détecté par l'IA (`LeadAIUnderstandingCard`)
A new card showing:
- **Résumé IA** — `lead.ai_summary` (full text in a violet-tinted block)
- **Intention** — `lead.intention` (badge with tone)
- **Urgence** — `lead.urgency` (badge with tone)
- **Sentiment** — `lead.sentiment` (badge with tone)

All fields show "Non disponible" if null/empty. The AI badge is clearly labeled "FlowPilot AI".

### Section 2c — Justification du score (`LeadScoreExplanationCard`)
A new card showing:
- Score displayed as `XX / 100` with a colored ring
- Priority badge
- **Facteurs positifs** — derived from real DB fields (sentiment=positive, urgency=high, intent=purchase-ready, priority=high, message present)
- **Facteurs de risque** — derived from real DB fields (sentiment=negative/neutral, urgency=low, intent=information-gathering, priority=low, message absent)

No hallucinated facts. All factors are computed from actual stored field values.

### Section 2c — Action commerciale recommandée (`LeadSalesActionCard`)
A new card showing:
- **Prochaine action** — `lead.next_action` (via `getCrmNextActionLabel`)
- **Recommandation IA** — `lead.recommended_action` (only shown if non-trivial)
- **Questions de qualification standard** — 5 static generic sales methodology questions, clearly labeled as "non générées par l'IA"

### Contact card improvement (`LeadBusinessProfile`)
Added two new fields:
- **Date de création** — `lead.created_at`
- **Dernier contact** — `lead.last_contact_at`

---

## 6. Business Value

| Before | After |
|---|---|
| Sales user sees score=38, priority=low | Sales user sees WHY score is 38 (low urgency, information-gathering intent, neutral sentiment) |
| No original message visible | Full client message displayed prominently |
| AI summary hidden in small chip | Full AI summary in dedicated violet card |
| No qualification guidance | 5 standard qualification questions always visible |
| Contact card missing dates | Contact card shows creation date and last contact date |

---

## 7. Files Modified

### Frontend — New components:
- `frontend/src/components/crm/lead-details/LeadClientRequestCard.tsx` *(new)*
- `frontend/src/components/crm/lead-details/LeadAIUnderstandingCard.tsx` *(new)*
- `frontend/src/components/crm/lead-details/LeadScoreExplanationCard.tsx` *(new)*
- `frontend/src/components/crm/lead-details/LeadSalesActionCard.tsx` *(new)*

### Frontend — Modified:
- `frontend/src/components/crm/lead-details/index.ts` — added 4 new exports
- `frontend/src/pages/CRMLeadDetailsPage.tsx` — added imports, added 4 new cards to layout, improved contact card

### Backend — No changes:
- No schema changes
- No API changes
- No migration needed
- No n8n callback changes

---

## 8. Validation Commands

```bash
# Frontend build (TypeScript + Vite)
cd frontend
npm run build

# Backend Python compile
python -m compileall backend/app
```

**Build result:** `✓ built in 446ms` — no TypeScript errors.

---

## 9. Manual Smoke Test Checklist

### Test 1 — Admin user, lead_003
1. Login as `admin@flowpilot.ai` / `FlowPilot@123`
2. Navigate to `/crm-lead-details?leadId=lead_003`
3. Verify:
   - [ ] Hero card shows: "Medina Services", score 38, priority Faible, status Lead
   - [ ] **Demande du client** card shows: "Please send information about your automation platform."
   - [ ] **Produit / service demandé** shows: "Automation Consulting"
   - [ ] **Source du lead** shows: "Email"
   - [ ] **Localisation** shows: "Sousse, Tunisia"
   - [ ] **Valeur estimée** shows: "2 500 TND"
   - [ ] **Besoin détecté par l'IA** card shows AI summary: "Early-stage lead with low urgency."
   - [ ] **Intention** badge shows: "Information-Gathering"
   - [ ] **Urgence** badge shows: "Faible"
   - [ ] **Sentiment** badge shows: "Neutre"
   - [ ] **Justification du score** shows score 38/100 with risk factors (low urgency, information-gathering, neutral sentiment)
   - [ ] **Action commerciale recommandée** shows next action and 5 qualification questions
   - [ ] Contact card shows email, phone, company, created date, last contact date
   - [ ] Activity timeline shows at least 1 interaction
   - [ ] No mock/fake data visible

### Test 2 — Sales user
1. Login as `sales@flowpilot.ai` / `FlowPilot@123`
2. Navigate to `/crm-lead-details?leadId=lead_001`
3. Verify:
   - [ ] Page loads with real data
   - [ ] All 4 new cards visible
   - [ ] RBAC actions work (generate draft, log interaction)

### Test 3 — Employee user (blocked)
1. Login as `employee@flowpilot.ai` / `FlowPilot@123`
2. Navigate to `/crm-lead-details?leadId=lead_001`
3. Verify:
   - [ ] CRM access is blocked (redirect or permission denied)

### Test 4 — Data integrity
1. Open browser DevTools → Network tab
2. Navigate to `/crm-lead-details?leadId=lead_003`
3. Find the API call to `/api/crm/leads/lead_003`
4. Verify:
   - [ ] Response contains `message`, `ai_summary`, `intention`, `urgency`, `sentiment`, `product_service`, `location`, `estimated_value`, `recommended_action`, `next_action`
   - [ ] UI values match API response exactly
   - [ ] No values in UI that don't exist in API response

---

## 10. Known Limitations

1. **Score reasoning** — The score explanation is derived from existing DB fields (sentiment, urgency, intent, priority, message presence). There is no dedicated `score_reasoning` text field in the DB. If the AI scoring agent stores detailed reasoning in the future, a `score_reasoning` column can be added to `crm_leads` and exposed in `CrmLeadDetail`.

2. **Need summary / pain points** — The DB does not have `need_summary` or `pain_points` columns. The `ai_summary` field serves this purpose. If more granular AI output is needed, these can be added as optional nullable columns via a safe migration.

3. **Qualification questions** — The 5 qualification questions are static/generic (standard sales methodology). They are clearly labeled as "Questions de qualification standard — non générées par l'IA". If the AI agent generates lead-specific qualification questions in the future, they can be stored in a new `qualification_questions` JSON column.

4. **Mock fallback** — When the backend is unreachable, the page falls back to mock data (existing behavior, not changed). The new cards show "Non disponible" in this state since `backendLead` is null.

5. **Offline banner** — When mock fallback is active, a yellow banner already warns the user. The new cards correctly show empty states in this scenario.
