# WhatsApp (Twilio)

Jarvis peut envoyer des messages WhatsApp par la voix ou depuis la page
Operator — toujours avec confirmation (doctrine 95/5 : un message écrit engage,
l'outil est classé **N3 critique**).

## 1. Créer le sender Twilio

1. Compte sur [twilio.com](https://www.twilio.com) (essai gratuit suffisant
   pour tester).
2. Console Twilio → **Messaging** → **Try it out** → **Send a WhatsApp message** :
   le sandbox te donne un numéro expéditeur (`whatsapp:+14155238886`).
   Pour envoyer à ton propre numéro, tu dois d'abord rejoindre le sandbox
   en envoyant « join <code> » depuis ton WhatsApp au numéro du sandbox.
3. Note l'**Account SID** (`AC...`) et l'**Auth Token** depuis la console.

## 2. Configuration

Dans `config.yaml` :

```yaml
whatsapp:
  sid: "ACxxxxxxxxxxxxxxxx"
  token: "ton_auth_token"
  expediteur: "whatsapp:+14155238886"
```

## 3. Utilisation

- Voix / chat écrit : « Hey Jarvis, envoie un WhatsApp au 06 12 34 56 78
  disant : rendez-vous confirmé à 15h »
- La carte de validation apparaît dans la conversation de l'Operator
  (« Je vais envoyer le message WhatsApp à +33612345678. Tu confirmes ? »)
  avec les boutons **Valider / Refuser**.

## Détails techniques

- `tools/whatsapp.py` — API REST Twilio (`/Messages.json`), sans dépendance
  supplémentaire (urllib).
- Numéros normalisés automatiquement : `06...` → `whatsapp:+336...`.
- Outil `envoyer_whatsapp`, confirmation obligatoire (N3), jamais autorisé
  en « toujours autoriser », jamais en auto à distance.
- Domaine de routage : les phrases contenant « whatsapp » exposent les
  outils `whatsapp` + `appels` au LLM.
