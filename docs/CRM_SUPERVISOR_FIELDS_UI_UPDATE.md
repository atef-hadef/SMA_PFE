# FlowPilot AI CRM Supervisor Fields UI Update

Date: 2026-04-30  
Status: Step 56.6 completed

## 1. Purpose

Step 56.6 updates the CRM API responses and CRM frontend pages so the CRM shows
useful business information, not only AI score data.

This step builds on Step 56.5, where the PostgreSQL schema was aligned with the
supervisor CRM requirements.

## 2. Backend fields added to API responses

`GET /api/crm/leads` now includes business fields in each list item:

- `id`
- `name`
- `company`
- `email`
- `phone`
- `source`
- `customer_status`
- `status`
- `score`
- `priority`
- `customer_category`
- `product_service`
- `estimated_value`
- `location`
- `is_active`
- `next_action`
- `assigned_to`
- `created_at`
- `last_contact_at`

`GET /api/crm/leads/{lead_id}` now includes full detail fields:

- `id`
- `name`
- `company`
- `email`
- `phone`
- `source`
- `customer_status`
- `status`
- `score`
- `sentiment`
- `urgency`
- `intention`
- `message`
- `ai_summary`
- `recommended_action`
- `assigned_to`
- `created_at`
- `last_contact_at`
- `next_action`
- `product_service`
- `estimated_value`
- `priority`
- `customer_category`
- `location`
- `is_active`
- `notes`
- `interaction_history`

The existing frontend aliases are preserved:

- `full_name` is returned as `name`
- `company_name` is returned as `company`
- `lead_score` is returned as `score`

## 3. Frontend sections added

`/crm-leads` now shows a business-friendly CRM table with:

- Lead / Client
- Company
- Customer Status
- Priority
- Estimated Value
- Source
- Next Action
- Status / Active

`/crm-lead-details` now shows:

- Client Information
- Commercial Tracking
- AI Analysis
- Interaction History

## 4. Supervisor requirement mapping

| Supervisor requirement | API/UI field |
| --- | --- |
| Full name | `name`, Client Information |
| Client ID | `id`, Client Information |
| Email | `email`, Client Information |
| Phone | `phone`, Client Information |
| Company / Organization | `company`, Client Information |
| Customer status | `customer_status`, Client Information and CRM Leads table |
| Lead source | `source`, Client Information and CRM Leads table |
| Sales owner / responsible person | `assigned_to`, Client Information |
| Creation date | `created_at`, Client Information |
| Last contact | `last_contact_at`, Commercial Tracking |
| Next action | `next_action`, Commercial Tracking and CRM Leads table |
| Interaction history | `interaction_history`, Interaction History |
| Product / Service associated | `product_service`, Commercial Tracking |
| Amount / Value | `estimated_value`, Commercial Tracking and CRM Leads table |
| Priority | `priority`, Commercial Tracking and CRM Leads table |
| Customer category | `customer_category`, Commercial Tracking |
| Location | `location`, Commercial Tracking |
| Active / inactive status | `is_active`, Client Information and CRM Leads table |
| Notes / Comments | `notes`, Commercial Tracking |

## 5. Routes tested

- `/crm-leads`
- `/crm-lead-details`

## 6. SQL verification

```sql
SELECT id, full_name, customer_status, next_action, product_service, estimated_value, priority, customer_category, location, is_active FROM crm_leads;
```

```sql
SELECT id, lead_id, interaction_type, channel, summary FROM crm_interactions;
```

## 7. Not implemented yet

- No n8n alignment
- No Odoo sync
- No real auth/RBAC
- No real CRM interaction creation from UI yet
