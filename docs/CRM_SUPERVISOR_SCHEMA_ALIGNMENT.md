# FlowPilot AI CRM Supervisor Schema Alignment

Date: 2026-04-30  
Status: Step 56.5 completed

## 1. Purpose

Step 56.5 aligns the PostgreSQL CRM schema with the supervisor CRM requirements.

The goal is to keep the MVP database useful for business review by storing more
than AI scoring data. CRM leads now include customer status, next sales action,
product/service context, estimated value, priority, category, location, active
status, and contact timing. A new `crm_interactions` table stores interaction
history for each lead.

This is a backend/database-only step.

## 2. Supervisor requirements covered

- Full name
- Client ID
- Email
- Phone
- Company / Organization
- Customer status
- Lead source
- Sales owner / responsible person
- Creation date
- Last contact
- Next action
- Interaction history
- Product / Service associated
- Amount / Value
- Priority
- Customer category: VIP, standard, new, etc.
- Location
- Active / inactive status
- Notes / Comments

## 3. `crm_leads` fields added

The existing `crm_leads` table was extended with:

- `customer_status`
- `last_contact_at`
- `next_action`
- `product_service`
- `estimated_value`
- `priority`
- `customer_category`
- `location`
- `is_active`

Existing CRM fields were kept:

- `id`
- `full_name`
- `company_name`
- `email`
- `phone`
- `source`
- `status`
- `lead_score`
- `sentiment`
- `urgency`
- `intention`
- `message`
- `ai_summary`
- `recommended_action`
- `owner_user_id`
- `assigned_to`
- `notes`
- `created_at`
- `updated_at`

## 4. `crm_interactions` table

The new `crm_interactions` table stores lead interaction history.

Fields:

- `id`
- `lead_id`
- `interaction_type`
- `channel`
- `summary`
- `interaction_date`
- `created_by`
- `created_at`
- `updated_at`

## 5. Requirement mapping

| Supervisor requirement | Database field |
| --- | --- |
| Full name | `crm_leads.full_name` |
| Client ID | `crm_leads.id` |
| Email | `crm_leads.email` |
| Phone | `crm_leads.phone` |
| Company / Organization | `crm_leads.company_name` |
| Customer status | `crm_leads.customer_status` |
| Lead source | `crm_leads.source` |
| Sales owner / responsible person | `crm_leads.owner_user_id`, `crm_leads.assigned_to` |
| Creation date | `crm_leads.created_at` |
| Last contact | `crm_leads.last_contact_at` |
| Next action | `crm_leads.next_action` |
| Interaction history | `crm_interactions` rows linked by `lead_id` |
| Product / Service associated | `crm_leads.product_service` |
| Amount / Value | `crm_leads.estimated_value` |
| Priority | `crm_leads.priority` |
| Customer category | `crm_leads.customer_category` |
| Location | `crm_leads.location` |
| Active / inactive status | `crm_leads.is_active` |
| Notes / Comments | `crm_leads.notes` |

## 6. Commands

From the project root:

```powershell
docker compose up -d postgres
```

From the `backend` folder:

```powershell
python scripts/upgrade_crm_schema.py
python scripts/seed_database.py
```

## 7. Verification SQL

```sql
SELECT id, full_name, customer_status, next_action, product_service, estimated_value, priority, customer_category, location, is_active FROM crm_leads;
```

```sql
SELECT id, lead_id, interaction_type, channel, summary FROM crm_interactions;
```

## 8. Not implemented yet

- No frontend update yet
- No n8n alignment yet
- No Odoo sync
- No real authentication/RBAC
