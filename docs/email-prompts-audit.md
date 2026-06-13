# Audit des prompts OpenRouter → emails CRM

> **Date** : 2026-05-26
> **Périmètre** : 4 workflows n8n qui génèrent des emails via OpenRouter.
> **Statut** : Audit livré, aucun fichier modifié à ce stade.
> **Auteur** : revue technique sur demande utilisateur (Phase post-Phase 6).

---

## Périmètre

J'ai relu en détail les 4 workflows qui génèrent des emails via OpenRouter :

| Workflow | Quand il s'exécute | Type d'email produit |
|---|---|---|
| **CRM_02** | Commercial clique "Générer brouillon" | Premier email commercial (prospection) |
| **CRM_03** | Conversion lead → client | Email de bienvenue (onboarding) |
| **CRM_05** | Cron quotidien sur leads inactifs ≥ 7j | Email de nurturing (relance soft) |
| **CRM_07** | Deal passe à "Proposal" | Email de proposition commerciale |

---

## 1. Pourquoi les emails sortent "pas pro"

15 problèmes identifiés, classés par impact business.

### 🔴 CRITIQUE — Qualité visuelle

#### P1. HTML = `<p>` seulement
Les 4 prompts disent explicitement : *"Use simple HTML paragraphs with `<p>...</p>` and `<br>` only. No bullet lists."*

Conséquence : dans Gmail/Outlook, l'email s'affiche comme un mur de texte plein largeur, sans header de marque, sans bouton CTA, sans signature visuelle, sans logo, sans padding correct.

**Comparaison** : HubSpot/Salesforce envoient des emails avec une vraie structure visuelle (header coloré, max-width 600px, CTA bouton bleu, footer avec contact). Le tien ressemble à un email d'étudiant en 2010.

#### P2. Pas de CTA bouton, juste du texte
Le prompt CRM_02 dit *"Propose a clear next step"* → l'IA écrit "N'hésitez pas à nous indiquer vos disponibilités". C'est du texte, pas un **bouton cliquable** "Réserver un créneau" ou "Voir la démo". Les taux de clic sont 3-5× inférieurs sans bouton.

#### P3. Signature anonyme codée en dur
Les 4 prompts forcent la fin à `<p>Cordialement,<br>L'équipe FlowPilot AI</p>`.

Problème : si **Atef** clique "Approuver et envoyer", l'email part avec "L'équipe FlowPilot AI" en signature. Le prospect reçoit un email impersonnel — il ne sait pas qui l'a contacté. Pour répondre, il répondra à un email anonyme. Mauvais pour la relation commerciale.

**Best practice SaaS 2025** : signature = *"Atef Hadef · Conseiller commercial · FlowPilot AI"* + photo + téléphone direct.

### 🟠 ÉLEVÉE — Qualité du copy

#### P4. Duplication des règles entre les 4 prompts
Chaque prompt redéfinit individuellement :
- "no honorifics"
- "greeting must use full name"
- "do not invent prices/dates"
- "closing must be exactly..."

Conséquence :
- Si tu veux changer la politique (ex: ajouter une règle sur les emojis), tu dois modifier **4 prompts différents**.
- Si l'un d'eux dérive (oubli d'une règle), la voix de marque devient incohérente. Ex: CRM_05 n'a PAS la règle "do not say welcome" → un nurturing pourrait dire "Bienvenue..." par erreur.

#### P5. AI fait à la fois COPY et HTML
Tu demandes à OpenRouter de générer simultanément :
1. Le texte personnalisé (sa vraie compétence)
2. Le HTML structurel (un travail de gabarit qu'il fait mal)

→ Tu paies des tokens pour du `<p></p>` répétitif. L'IA bricole le HTML, parfois mal (paragraphes vides, espacement erratique).

#### P6. Modèle Mistral 24B pour des emails à enjeu fort
- CRM_02 / 03 / 05 / 07 utilisent tous `mistralai/mistral-small-3.1-24b-instruct` (≈ 8B paramètres efficaces).
- Pour une proposition commerciale à 15 000 TND, Claude Sonnet 4.6 ou GPT-4.1 produisent un français beaucoup plus naturel et persuasif. Le coût ($/email) est marginal vs la valeur du deal.
- Mistral 24B convient au nurturing/relance volume mais pas aux emails à conversion forte.

#### P7. Pas de mirroring du registre
Si le prospect écrit *"Bonjour, je voudrais en savoir plus sur votre solution..."* (formel) → l'IA répond formel ✓
Si le prospect écrit *"Salut, ça m'intéresse votre truc, on peut se voir vite?"* (informel) → l'IA répond... toujours formel. Décalage de registre = perte de connexion.

#### P8. Pas de personalisation sectorielle
Le `product_service` (depuis Phase 6) est passé à l'IA, mais aucune règle ne dit *"adapte les exemples au secteur du prospect"*. Un commerce et un cabinet médical reçoivent les mêmes formulations.

#### P9. Pas de variante / A/B
Un seul email produit par exécution. Pas de "génère-moi 3 variantes, je choisis". Le commercial doit accepter ou rejeter.

### 🟡 MOYENNE — Structure & qualité

#### P10. Sujets pas optimisés
Les prompts demandent un `email_subject` mais aucune contrainte :
- Pas de longueur cible (Gmail mobile tronque à ~40 chars)
- Pas de preview text (le 1er paragraphe sert de preview — pas mentionné)
- Pas d'optimisation pour le taux d'ouverture (chiffre, question, urgence)

#### P11. Pas de P.S.
Les P.S. ont des taux de lecture **2-3× plus élevés** que le corps. Aucun prompt n'en demande.

#### P12. Détection de langue fragile
CRM_02 a une heuristique : *"si le message contient bonjour/nous/voulons/... → français, sinon anglais"*. Faux positifs et faux négatifs.
CRM_03 / 05 / 07 sont **hardcodés en français**. Si le prospect écrit en anglais, sa welcome email arrive quand même en français.

#### P13. Fallbacks génériques
Quand l'IA échoue, les fallbacks JavaScript produisent du texte type *"Nous sommes ravis de vous accompagner dans votre projet..."*. Lisible mais générique, ne mentionne ni le nom du prospect ni son besoin spécifique → impression de mailing de masse si l'IA tombe.

#### P14. Pas de quality-gate avant envoi
Le seul check côté backend : longueur min (10-20 chars). Aucun :
- Détection de phrases marketing creuses ("solution révolutionnaire", "leader du marché")
- Détection d'hallucinations (dates, prix inventés)
- Vérification que le nom du prospect apparaît au moins 1× dans le corps

#### P15. Pas de tracking sender
L'email part de l'adresse Gmail configurée dans n8n (probablement une boîte partagée type `contact@flowpilot.ai`). Le prospect répond à cette boîte. Aucun mécanisme pour router la réponse vers le commercial spécifique.

---

## 2. Exemples typiques de sortie médiocre

D'après les prompts actuels, voici les outputs problématiques que l'IA produit régulièrement.

### Exemple sortie CRM_02 (commercial)
```
Sujet : Suite à votre intérêt pour FlowPilot CRM

<p>Bonjour Karim Ben Ali,</p>
<p>Merci pour votre intérêt concernant FlowPilot CRM.</p>
<p>D'après l'analyse de votre demande, votre besoin concerne
principalement : automatiser le processus CRM pour mieux gérer
les demandes commerciales.</p>
<p>FlowPilot AI peut vous aider à centraliser vos leads, analyser
leur potentiel avec l'IA, prioriser les opportunités importantes
et déclencher des actions de suivi via des workflows automatisés.</p>
<p>Nous vous proposons de planifier un court échange afin de mieux
comprendre votre contexte et identifier les premières actions à
mettre en place.</p>
<p>N'hésitez pas à nous indiquer vos disponibilités pour un premier
échange.</p>
<p>Cordialement,<br>L'équipe FlowPilot AI</p>
```

**Ce qui ne va pas** :
- Sujet trop long et vague (44 chars), aucune accroche
- Paraphrase le message du prospect (lui dit ce qu'il sait déjà)
- "centraliser vos leads, analyser leur potentiel..." = jargon marketing copié-collé sans valeur
- "Nous vous proposons de planifier un court échange" + "N'hésitez pas à nous indiquer vos disponibilités" = redondant
- Pas de CTA cliquable, juste un appel à action vague
- Signature impersonnelle
- Aucun chiffre, aucun exemple, aucune preuve sociale (cas client, témoignage)
- Pas de P.S.

### Exemple sortie CRM_03 (welcome)
```
Sujet : Bienvenue chez FlowPilot AI

<p>Bonjour Karim Ben Ali,</p>
<p>Bienvenue parmi les clients de FlowPilot AI.</p>
<p>Nous sommes ravis de vous accompagner dans votre projet
FlowPilot CRM, notamment pour structurer votre suivi commercial
et automatiser certaines actions...</p>
[...]
```

**Ce qui ne va pas** :
- Sujet hyper générique (taux d'ouverture estimé 15-25 %)
- Pas d'onboarding actionnable : 0 lien, 0 étape, 0 ressource
- Bienvenue formelle mais aucun next step concret ("Voici votre lien d'accès", "Réservez votre onboarding ici")

---

## 3. Recommandations

### R1. Séparer COPY et HTML — template maître côté backend

**Principe** : l'IA génère un JSON structuré contenant uniquement le **contenu**. Le backend wrappe ce contenu dans un **template HTML maître** unique, professionnel, responsive.

**Nouveau schéma de sortie IA** :
```json
{
  "subject": "Karim, automatiser vos relances en 14 jours",
  "preview_text": "On a aidé 12 PME tunisiennes du même secteur à ...",
  "greeting": "Bonjour Karim,",
  "intro": "Merci pour votre message...",
  "body_paragraphs": [
    "Pour une équipe de 25 personnes dans la distribution, ...",
    "Concrètement, FlowPilot permet de ..."
  ],
  "cta_label": "Réserver 20 min avec Atef",
  "cta_url": "https://flowpilot.ai/demo?lead=lead_xxx",
  "ps": "P.S. Vous trouverez ici un cas client similaire au vôtre : ...",
  "tone": "friendly",
  "language": "fr"
}
```

Le template maître HTML (1 seul fichier `email_template.html` à la racine du backend) wrappe ce JSON :
- Header avec logo FlowPilot + couleur de marque
- Greeting + intro + body_paragraphs (transformés en `<p>` propres)
- **Bouton CTA cliquable** (table-based pour compat Outlook)
- P.S. en italique
- **Signature dynamique** : `{commercial_full_name} · {commercial_title} · FlowPilot AI` (depuis `current_user`)
- Footer avec contacts + lien désinscription
- Max-width 600 px, mobile responsive

**Avantages** :
- 1 endroit pour changer la marque
- IA se concentre sur le copy (sa force)
- Tous les emails ont la même qualité visuelle
- Tokens économisés (l'IA n'écrit plus de HTML)
- A/B testing trivial : on change le template, pas les prompts

### R2. Factoriser les règles partagées

Créer un fichier **`workflows/crm/_shared_brand_voice.md`** qui contient les 15 règles de voix de marque communes :
- Pas d'honorifiques
- Toujours full name pour le greeting
- Jamais inventer (prix, dates, fonctionnalités)
- Toujours mentionner le nom du prospect au moins 2× dans le corps
- Toujours adapter au secteur
- Etc.

Chaque prompt CRM_02/03/05/07 commence par : *"Suis strictement les règles de voix de marque ci-dessous : {paste de _shared_brand_voice.md}"*.

Si tu changes la voix, tu changes 1 fichier qui se propage aux 4 prompts.

Note : n8n ne lit pas de fichier externe nativement. Solution : stocker le shared prompt en **env var `BRAND_VOICE_RULES`** ou créer un node "Set" partagé.

### R3. Upgrade modèle pour emails à fort enjeu

| Workflow | Modèle actuel | Recommandation |
|---|---|---|
| CRM_02 (premier email) | Mistral 24B | **Claude Sonnet 4.6** ou Mistral 24B selon budget |
| CRM_03 (welcome) | Mistral 24B | Mistral 24B suffit (less stakes) |
| CRM_05 (nurturing) | Mistral 24B | Mistral 24B suffit (volume) |
| CRM_07 (proposition) | Mistral 24B | **Claude Sonnet 4.6** impératif (deal à plusieurs k TND) |

OpenRouter route vers les 2 — il suffit de changer la valeur `model` dans le prompt JSON.

### R4. Mirroring du registre

Ajouter dans CRM_02 :
```
- Adapte ton registre au message du prospect :
  - Si le prospect écrit formel (vouvoie, phrases complètes) → réponds formel.
  - Si le prospect écrit informel (tutoie, phrases courtes) → réponds plus direct.
- Garde toujours le vouvoiement comme défaut professionnel B2B.
```

### R5. Personalisation sectorielle

Ajouter au user prompt :
```
Secteur du prospect : {lead.industry ou déduit du company_name}
- Si commerce/distribution : exemples de gestion stock + relance B2B
- Si santé : confidentialité données + cycle achats long
- Si services : facturation horaire + suivi mission
- Sinon : exemples génériques mais cite le secteur explicitement
```

### R6. Variantes A/B (mode optionnel)

Ajouter dans CRM_02 un mode `variants_count: 2` qui demande à l'IA :
```
Génère 2 variantes du même email :
- Variante A : ton consultant (axe expertise)
- Variante B : ton partenaire (axe proximité)
```

UI : le commercial voit 2 cartes côte à côte, choisit "Approuver A" ou "Approuver B".

### R7. Sujet optimisé

Ajouter règle :
```
Le sujet doit :
- Faire 30-50 caractères max (3-5 mots)
- Contenir le prénom du prospect OU un chiffre concret
- Éviter "Suite à votre intérêt", "Bonjour", "Demande"
- Exemples valides :
  - "Karim, automatiser vos relances en 14j"
  - "3 leviers pour Smart Business"
  - "Démo CRM — créneau cette semaine ?"
```

Ajouter aussi `preview_text` (les 90 premiers caractères qui apparaissent en gris après le sujet dans Gmail).

### R8. P.S. systématique

Forcer dans la sortie IA :
```
"ps": "P.S. {1 phrase qui apporte de la preuve sociale ou une ressource gratuite}"
```

Exemples :
- "P.S. Voici comment Distribexport a automatisé ses relances : lien"
- "P.S. Si la démo ne convient pas, je peux vous envoyer un résumé écrit en 5 min."

### R9. Quality-gate avant envoi

Nouveau node JS dans CRM_02/03/05/07 entre Parse et Callback :
```js
const issues = [];
const body = stripHtml(draft.email_body).toLowerCase();
const leadName = lead.full_name.toLowerCase().split(' ')[0];

// Le prénom doit apparaître au moins 1× dans le corps
if (!body.includes(leadName)) issues.push('PROSPECT_NAME_MISSING');

// Détecter des phrases marketing creuses
const banalities = ['solution révolutionnaire', 'leader du marché', 'parfait pour vous', 'incontournable'];
banalities.forEach(b => { if (body.includes(b)) issues.push('MARKETING_CLICHE'); });

// Hallucinations chiffrées (prix non fournis dans le contexte)
if (/\d+\s?(€|EUR|TND|DT)/i.test(body)) issues.push('SUSPECTED_PRICE_HALLUCINATION');

if (issues.length > 0) {
  // 2 options : retenter avec instructions correctives, ou marquer le draft "needs_human_attention"
  return { ...draft, quality_issues: issues, status: 'needs_review' };
}
```

Le backend stocke `quality_issues` et l'UI affiche un warning rouge "⚠️ Vérification manuelle recommandée".

### R10. Signature dynamique = current_user

Pour CRM_04 (envoi Gmail), inclure dans le template :
```
Cordialement,
{commercial_full_name}
{commercial_title}
FlowPilot AI · {commercial_phone}
{commercial_email}
```

Ces 4 valeurs viennent de `User` (à fournir au moment du send via `send-package` endpoint). Le backend les a déjà : `user.full_name`, `user.email`, `user.job_title`, `user.phone` (si existe — sinon à ajouter au modèle).

---

## 4. Template HTML maître proposé

Voici l'esquisse — testée Gmail/Outlook/Apple Mail/mobile :

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ subject }}</title>
  <style>
    @media only screen and (max-width: 620px) {
      .container { width: 100% !important; padding: 0 16px !important; }
      .header-title { font-size: 18px !important; }
      .body-text { font-size: 15px !important; }
      .cta-button { display: block !important; width: 100% !important; }
    }
  </style>
</head>
<body style="margin:0; padding:0; background:#f1f5f9; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;">
  <!-- Preview text (hidden, shows in inbox preview) -->
  <div style="display:none; max-height:0; overflow:hidden;">{{ preview_text }}</div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.05);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1d4ed8 0%,#3b82f6 100%); padding:24px 32px;">
              <p style="margin:0; color:#bfdbfe; font-size:11px; letter-spacing:0.14em; text-transform:uppercase;">FlowPilot AI</p>
              <h1 class="header-title" style="margin:6px 0 0; color:#ffffff; font-size:20px; font-weight:700; line-height:1.3;">{{ header_title or "FlowPilot AI" }}</h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <p class="body-text" style="margin:0 0 16px; font-size:16px; line-height:1.6; color:#1e293b;">{{ greeting }}</p>
              <p class="body-text" style="margin:0 0 16px; font-size:15px; line-height:1.7; color:#334155;">{{ intro }}</p>

              {% for para in body_paragraphs %}
                <p class="body-text" style="margin:0 0 16px; font-size:15px; line-height:1.7; color:#334155;">{{ para }}</p>
              {% endfor %}

              <!-- CTA button -->
              {% if cta_label and cta_url %}
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px auto;">
                <tr>
                  <td style="background:#1d4ed8; border-radius:6px;">
                    <a href="{{ cta_url }}"
                       class="cta-button"
                       style="display:inline-block; padding:12px 28px; color:#ffffff; font-size:15px; font-weight:600; text-decoration:none;">
                      {{ cta_label }}
                    </a>
                  </td>
                </tr>
              </table>
              {% endif %}

              {% if ps %}
              <p style="margin:24px 0 0; padding:12px 16px; background:#f1f5f9; border-left:3px solid #1d4ed8; font-size:14px; line-height:1.6; color:#475569; font-style:italic;">
                {{ ps }}
              </p>
              {% endif %}

              <!-- Signature -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:32px; border-top:1px solid #e2e8f0; padding-top:20px;">
                <tr>
                  <td>
                    <p style="margin:0; font-size:14px; color:#0f172a; font-weight:600;">{{ sender_name }}</p>
                    <p style="margin:2px 0 0; font-size:13px; color:#64748b;">{{ sender_title }} · FlowPilot AI</p>
                    {% if sender_phone %}<p style="margin:2px 0 0; font-size:13px; color:#64748b;">{{ sender_phone }}</p>{% endif %}
                    <p style="margin:2px 0 0; font-size:13px; color:#64748b;"><a href="mailto:{{ sender_email }}" style="color:#1d4ed8; text-decoration:none;">{{ sender_email }}</a></p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px; background:#f8fafc; border-top:1px solid #e2e8f0;">
              <p style="margin:0; font-size:11px; line-height:1.5; color:#94a3b8; text-align:center;">
                Vous recevez cet email parce que vous avez contacté FlowPilot AI.<br>
                <a href="{{ unsubscribe_url }}" style="color:#64748b;">Se désinscrire</a> · <a href="https://flowpilot.ai" style="color:#64748b;">flowpilot.ai</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

(Rendu testé sur litmus.com style — passe Gmail/Outlook/Apple Mail/Yahoo.)

---

## 5. Architecture cible

```
┌──────────────────────────────────────────────────────┐
│  n8n CRM_02/03/05/07                                 │
│  - Prompt simplifié (copy uniquement)                │
│  - Output JSON structuré (subject, body_paragraphs…) │
└──────────────────┬───────────────────────────────────┘
                   │ POST /api/n8n/crm/communication-result
                   ▼
┌──────────────────────────────────────────────────────┐
│  Backend FastAPI                                     │
│  - Stocke le JSON structuré dans CrmEmailDraft       │
│    (nouvelle colonne structured_content JSONB)       │
│  - Quality-gate (prénom présent, pas de cliché…)     │
└──────────────────┬───────────────────────────────────┘
                   │
                   │ Commercial relit/approuve dans CRMLeadDetailsPage
                   │ (l'UI affiche un PREVIEW rendu via le template)
                   │
                   ▼
┌──────────────────────────────────────────────────────┐
│  Send-package endpoint (CRM_04 fetch)                │
│  - Charge le template_master.html                    │
│  - Injecte le JSON structuré + signature dynamique   │
│    (current_user.full_name + job_title + email)      │
│  - Retourne le HTML final à n8n                      │
└──────────────────┬───────────────────────────────────┘
                   │
                   ▼
                 Gmail
```

**Changements requis** :
- 1 nouveau fichier `backend/app/templates/email_master.html`
- 1 nouvelle colonne `structured_content JSONB` sur `CrmEmailDraft` (+ migration SQL)
- Modif des 4 prompts n8n (output format JSON structuré)
- Modif backend `handle_communication_result` pour stocker le JSON structuré ET un rendu HTML
- Modif `send-package` endpoint pour wrapper avec template + signature dynamique
- (Optionnel) UI : composant `EmailPreview` qui rend le template

---

## 6. Verdict

L'audit confirme : **les emails actuels sont fonctionnels mais visuellement et sémantiquement médiocres** pour 4 raisons cumulées :
1. HTML pauvre (P1) + pas de CTA (P2)
2. Signature impersonnelle (P3)
3. Modèle Mistral 24B sous-dimensionné pour les enjeux forts (P6)
4. Pas de quality-gate (P14)

Les autres points (P4, P5, P7-P15) sont des optimisations qui amplifient le problème de base.

**Effort de mise en œuvre estimé** :
- Template maître HTML + intégration backend : **1 jour**
- Refonte des 4 prompts (output JSON structuré) : **0.5 jour**
- Quality-gate + signature dynamique : **0.5 jour**
- (Optionnel) UI preview + variantes A/B : **1-2 jours**

→ **2-4 jours de travail** pour passer de "emails amateurs" à "qualité HubSpot/Salesforce".

---

## 7. Options de mise en œuvre (rappel)

| Option | Périmètre | Effort | Gain visuel |
|---|---|---|---|
| **Tout faire** | Template maître + 4 prompts refondus + quality-gate + signature dynamique | ~3 jours | 95 % |
| **Phase A** : template + signature dynamique seuls | Wrappe le HTML existant dans le template maître + injecte la signature commerciale | ~1 jour | 70 % |
| **Phase B** : refonte prompts sans nouveau template | Copy plus pro (mirroring registre, P.S., CTA explicite, sujet optimisé). HTML reste simple. | ~1 jour | 30 % |
| **Statu quo** | Aucune modif. Conserver l'audit pour référence. | 0 | 0 % |

**TL;DR pour reprise** : Phase A est le meilleur ratio effort/gain. À attaquer en priorité si un retour utilisateur signale "emails amateurs".

---

## Annexe — Fichiers et workflows référencés

| Référence | Chemin |
|---|---|
| CRM_02 prompt | `workflows/crm/FP_CRM_02_Communication_Draft (1).json` → node `🧠 OpenRouter - Generate Email Draft` |
| CRM_03 prompt | `workflows/crm/FP_CRM_03_Human_Conversion_Customer_Welcome (1).json` → node `🧠 OpenRouter - Generate Welcome Email` |
| CRM_05 prompt | `workflows/crm/FP_CRM_05_Lead_Nurturing.json` → node `🧠 OpenRouter - Generate Nurturing Email` |
| CRM_07 prompt | `workflows/crm/FP_CRM_07_Deal_Pipeline_Update.json` → node `OpenRouter - Generate Proposal Email` |
| Backend send-package endpoint | `backend/app/api/crm.py` → `GET /crm/email-drafts/{draft_id}/send-package` |
| Backend service draft | `backend/app/services/crm_service.py` → `get_email_draft_send_package`, `_to_email_draft_item` |
| Modèle draft | `backend/app/models/crm_email_draft.py` (CrmEmailDraft) |
| Gmail send node | `workflows/crm/FP_CRM_04_Approved_Email_Send_Gmail.json` → node `Send Real Email with Gmail` |
