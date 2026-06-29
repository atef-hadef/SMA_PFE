# Configuration n8n pour Standalone

## Variables d'environnement à définir dans n8n

Dans n8n → Settings → Variables (ou via le fichier `n8n.env` du docker-compose),
définir :

```env
FLOWPILOT_API_BASE_URL=http://host.docker.internal:8000
FLOWPILOT_N8N_SHARED_SECRET=flowpilot-test-secret
OPENROUTER_API_KEY=<ta clé OpenRouter>
```

> Dans ce projet, `n8n.env` contenait historiquement `FLOWPILOT_INTERNAL_SECRET`
> (mauvais nom). Les workflows `leave_standalone` lisent
> `$env.FLOWPILOT_N8N_SHARED_SECRET` : c'est **ce nom exact** qui doit être défini.
> La variable a été ajoutée (l'ancienne est conservée pour les workflows CRM).

## ⚠️ CRITIQUE : cohérence du secret

`FLOWPILOT_N8N_SHARED_SECRET` doit être **EXACTEMENT identique** entre :

| Où | Variable | Rôle |
|---|---|---|
| `backend/.env` | `FLOWPILOT_N8N_SHARED_SECRET` | Lu par FastAPI (`require_internal_secret`) |
| `n8n.env` | `FLOWPILOT_N8N_SHARED_SECRET` | Utilisé par les workflows pour signer les callbacks (`X-FlowPilot-Secret`) |

Si différent (ou absent côté n8n) → les callbacks
`/api/n8n/leave-standalone/*` sont rejetés avec **401 Unauthorized**.

Valeur actuelle du projet : `flowpilot-test-secret` (alignée des deux côtés).

> Pour renforcer le secret, changer la valeur dans **les deux fichiers en même
> temps** (ex. `tac-tic-pfe-2026-secret-key-flowpilot`) puis redémarrer backend + n8n.

## Test de cohérence du secret

```bash
curl -X POST http://localhost:8000/api/n8n/leave-standalone/analysis-complete \
  -H "X-FlowPilot-Secret: flowpilot-test-secret" \
  -H "Content-Type: application/json" \
  -d '{"leave_request_id":"test"}'
```

- **200** `{"success": true, "message": "Leave request not found"}` → secret **OK**
  (la demande `test` n'existe pas, ce qui est normal).
- **401** `Invalid FlowPilot integration secret.` → secret **KO**, à corriger.

> Note : l'endpoint renvoie 200 (et non 404) pour un id inconnu — le callback est
> volontairement tolérant pour ne pas faire échouer n8n. Le 401 est le seul signal
> d'un secret incorrect.

## Workflows à activer

- `FP_LEAVE_STANDALONE_01_Notify_Manager` → **Active**
- `FP_LEAVE_STANDALONE_02_Notify_Employee` → **Active**

Voir [SWITCH_TO_STANDALONE.md](./SWITCH_TO_STANDALONE.md) pour la procédure complète.
