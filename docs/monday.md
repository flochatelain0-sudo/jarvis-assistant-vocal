# monday.com — le CRM de Jarvis

Jarvis lit et écrit dans ton CRM monday.com, à la voix et depuis la page
Operator (`http://localhost:8790/operator` → section « CRM monday.com »).

## Configuration (2 minutes)

1. **Le token API** — dans monday.com : avatar (en haut à droite) →
   *Developers* → *My access tokens* → créer un token (droits `boards:read`,
   `boards:write`). Copie-le.
2. **L'ID du tableau** — ouvre ton board principal dans monday.com ;
   l'URL ressemble à `monday.com/boards/1234567890` : l'ID est `1234567890`.
3. Dans `config.yaml` (jamais versionné — tes secrets restent chez toi) :

```yaml
monday:
  token: "eyJhbGciOi..."        # ton token, tel quel
  tableau: 1234567890            # l'ID du board principal
```

4. Redémarre Jarvis, puis : « Hey Jarvis, où j'en suis sur mon CRM ? »

## À la voix

| Tu dis | Jarvis fait |
|---|---|
| « mes tableaux monday » | liste tes boards (ID + nom) |
| « où j'en suis sur mes clients / mon CRM » | lit les items et résume |
| « ajoute le client Acme dans monday » | **demande confirmation**, puis crée l'item |
| « passe Acme en signé dans monday » | **demande confirmation**, puis modifie |

Doctrine 95/5 : la **lecture** est libre (N1), l'**écriture** exige ton feu
vert (N2) — la même file de confirmation que pour l'envoi de mails. Tu peux
aussi valider depuis la page Operator.

## Sur la page Operator

La section « CRM monday.com » affiche les items de ton tableau principal,
rafraîchis à l'ouverture. Si tu vois « non configuré », vérifie `config.yaml`.

## Sécurité

- `mcp_expose=False` : le CRM n'est **jamais** exposé aux agents externes
  (Hermes, MCP, pont iPhone).
- Le token ne sort jamais des appels API : jamais loggé, jamais prononcé,
  jamais écrit dans le journal Operator.
- Les noms de clients et montants ne sont pas journalisés (contenu sensible).
