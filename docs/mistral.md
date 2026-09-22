# 🇫🇷 Mistral AI comme modèle cloud de Jarvis

Jarvis peut parler à **Mistral AI** (La Plateforme, `console.mistral.ai`) au
lieu d'OpenAI ou de Claude. L'API Mistral est compatible OpenAI : le même
client, une `base_url` différente — aucun abonnement ChatGPT/Claude requis.

La voix, elle, est **locale par défaut** (Piper) — mais Jarvis peut
maintenant utiliser **Voxtral**, la synthèse vocale de Mistral : c'est la
même voix que Le Chat. Voir [local.md](local.md) et la section
« La voix de Le Chat (Voxtral) » plus bas.

## Configuration

Dans `config.yaml` :

```yaml
cloud:
  fournisseur: mistral

mistral:
  cle: "TA-CLE"                 # console.mistral.ai -> API keys
  modele: "mistral-small-latest"        # mode hybride : rapide, economique
  modele_qualite: "mistral-large-latest"  # mode qualite : le plus fort
  max_tokens: 2048
```

Puis relance Jarvis. Le message de démarrage doit afficher
`provider LLM : Mistral (mode hybride, modele mistral-small-latest)`.

## La voix de Le Chat (Voxtral)

Voxtral TTS (`voxtral-mini-tts-2603`) est le modèle de synthèse vocale de
Mistral : c'est lui qui parle dans Le Chat. Français natif, très expressif,
~90 ms de latence, 0,016 $ / 1000 caractères facturés sur le crédit du plan
Mistral (pas de pay-as-you-go : l'Auto Recharge désactivée bloque tout
dépassement).

Dans `config.yaml` :

```yaml
tts:
  moteur: voxtral

voxtral:
  modele: "voxtral-mini-tts-2603"
  voix: "fr_female"        # ou "fr_male", "casual_female", "casual_male"...
```

- `voix` accepte un **preset du modèle** (`fr_female`, `fr_male`,
  `casual_female`, `casual_male`, `cheerful_female`, `neutral_male`, ...) ou
  l'**identifiant d'une voix clonée** créée dans le Mistral Studio
  (console.mistral.ai → Build → Audio : 3–10 s d'audio suffisent pour
  cloner une voix, l'ID se colle dans `voxtral.voix`).
- La clé API est celle du LLM (`mistral.cle`) — aucune nouvelle dépendance,
  l'appel passe directement par l'API REST de Mistral.
- Si l'appel échoue (réseau, crédit épuisé, modération 403), Jarvis
  retombe automatiquement sur la voix de l'OS, comme pour Piper/Kokoro.
- Le mode `local` garde Piper/Kokoro : Voxtral ne s'active que si tu
  l'écris explicitement (`tts.moteur: voxtral`).

## Quels modèles ?

| Rôle | Modèle | Pourquoi |
|---|---|---|
| hybride (défaut) | `mistral-small-latest` | rapide, peu cher, bon function calling |
| qualité | `mistral-large-latest` | le plus capable de la famille |
| vision | `pixtral-large-latest` | capture d'écran / analyse d'image |

`*-latest` suit automatiquement les mises à jour de Mistral ; remplace par
une version épinglée (ex. `mistral-small-2503`) si tu veux un comportement
figé.

## Ce qui marche

- **Boucle vocale complète** : Whisper capte, Mistral raisonne et appelle
  les outils (domotique, OBS, navigateur…), Piper parle.
- **Appels d'outils** (function calling) : natif, y compris en parallèle.
- **Vision** : les captures d'écran passent par `pixtral` — configure
  `astra_pc.modele: pixtral-large-latest` pour le contrôle souris/clavier.
- **Sous-pipelines** : réservations, appels téléphoniques, indexation —
  tout ce qui passe par `core/cloud.py` suit le fournisseur actif.

## Ce qui ne change pas

- La facturation se suit dans le budget Jarvis (`mon_budget`) : prix au
  million de tokens, ajustables dans `config.yaml` (`budget.prix`).
- Ollama reste le mode 100 % local ; Gemini reste l'alternative gratuite.
- `mistral.url` permet de pointer vers un endpoint compatible (proxie,
  auto-hébergé) si tu en as un.
