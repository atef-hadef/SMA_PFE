-- Migration TAC-TIC : refonte des utilisateurs CRM + redistribution des données démo.
-- Idempotent : peut être rejoué sans danger sur une base déjà migrée.
--
-- NB : les mots de passe (TacTic2026!) sont (re)hashés par le seed applicatif au
--      démarrage (hash_password = pbkdf2_sha256 avec sel aléatoire, non
--      reproductible en SQL pur). Cette migration couvre l'identité des users et
--      la réaffectation des données démo ; relancer le backend (seed) met à jour
--      les password_hash.

BEGIN;

-- =========================================================================
-- 1. ADMIN — Atef Ben Hadef (ex "FlowPilot Admin")
-- =========================================================================
UPDATE users SET full_name='Admin', email='admin@tac-tic.tn',
    role_id='role_admin', job_title='Directeur Général', department='Direction',
    status='active'
WHERE id='user_001';

-- Nettoyage des noms/emails hérités "FlowPilot ..." sur les modules congés / IA
UPDATE users SET full_name='HR', email='hr@tac-tic.tn' WHERE id='user_040';
UPDATE users SET full_name='AI Supervisor', email='ai.supervisor@tac-tic.tn' WHERE id='user_050';

-- =========================================================================
-- 2. MANAGER — Manager Commercial (nouvel utilisateur)
-- =========================================================================
INSERT INTO users (id, full_name, email, role_id, status, job_title, department, created_at, updated_at)
VALUES ('user_002', 'Manager Commercial', 'manager.commercial@tac-tic.tn', 'role_manager', 'active',
        'Manager Commercial', 'Commercial', now(), now())
ON CONFLICT (id) DO UPDATE SET
    full_name=EXCLUDED.full_name, email=EXCLUDED.email, role_id=EXCLUDED.role_id,
    job_title=EXCLUDED.job_title, department=EXCLUDED.department, status='active';

-- =========================================================================
-- 3-5. COMMERCIAUX (role_sales)
-- =========================================================================
UPDATE users SET full_name='Commercial 1', email='commercial1@tac-tic.tn',
    role_id='role_sales', job_title='Conseiller Commercial', department='Commercial',
    status='active'
WHERE id='user_010';

UPDATE users SET full_name='Commercial 2', email='commercial2@tac-tic.tn',
    role_id='role_sales', job_title='Conseillère Commerciale', department='Commercial',
    status='active'
WHERE id='user_020';

UPDATE users SET full_name='Commercial 3', email='commercial3@tac-tic.tn',
    role_id='role_sales', job_title='Conseiller Commercial', department='Commercial',
    status='active'
WHERE id='user_030';

-- =========================================================================
-- 6. REDISTRIBUTION DES DONNÉES DÉMO sur les 3 commerciaux
--    (chaque commercial = 1 lead + sa tâche + son deal)
-- =========================================================================

-- Leads
UPDATE crm_leads SET owner_user_id='user_010', assigned_to='user_010' WHERE id='lead_001';
UPDATE crm_leads SET owner_user_id='user_020', assigned_to='user_020' WHERE id='lead_002';
UPDATE crm_leads SET owner_user_id='user_030', assigned_to='user_030' WHERE id='lead_003';

-- Interactions
UPDATE crm_interactions SET created_by='user_010' WHERE id IN ('interaction_001', 'interaction_002');
UPDATE crm_interactions SET created_by='user_020' WHERE id='interaction_003';

-- Tâches (task_002 reste sur user_030 / Yassine)
UPDATE crm_tasks SET owner_user_id='user_020', created_by='user_020' WHERE id='task_001';
UPDATE crm_tasks SET owner_user_id='user_010', created_by='user_010' WHERE id='task_003';

-- Deals
UPDATE crm_deals SET owner_user_id='user_010' WHERE id='deal_001';
UPDATE crm_deals SET owner_user_id='user_020' WHERE id='deal_002';

COMMIT;

-- Vérification post-migration :
--   SELECT id, full_name, email, role_id, status FROM users ORDER BY id;
