# Fournisseurs cloud : OpenAI et Claude/Anthropic

Jarvis sépare le **mode de routage** du **fournisseur cloud**. OpenAI et
Claude/Anthropic sont intégrés aujourd'hui. Gemini n'a pas encore de connecteur
natif ; il ne faut donc pas le présenter comme disponible tant que ce connecteur
n'est pas ajouté.

## OpenAI

Jarvis utilise l'API **Responses** d'OpenAI pour la conversation, la vision et les
appels d'outils. Le modèle recommandé au quotidien est `gpt-5.6-terra` ;
`gpt-6-astra` est disponible pour le mode qualité.

## Point important : ChatGPT et l'API sont séparés

Un abonnement ChatGPT (Plus, Pro, etc.) ne fournit pas automatiquement un solde
API. Jarvis a besoin d'une **clé API Platform** et d'une facturation API active.
Les crédits achetés dans ChatGPT/Codex ne sont pas des crédits API.

1. Ouvre <https://platform.openai.com/api-keys> et crée une clé de projet.
2. Vérifie la facturation sur <https://platform.openai.com/settings/organization/billing>.
3. Ajoute la clé uniquement dans `config.yaml` (ce fichier est gitignoré) :

```yaml
cloud:
  fournisseur: openai

openai:
  cle: "sk-proj-..."
  modele: "gpt-5.6-terra"
  modele_qualite: "gpt-6-astra"
  raisonnement: low
  raisonnement_qualite: high
```

Ne mets jamais la clé dans une issue, un commit, une capture d'écran ou
l'environnement d'Hermes.

## Changer de modèle depuis le panneau

Ouvre <http://localhost:8790/panneau>, onglet **Modèles** :

- **Hybride** active le modèle choisi pour les demandes quotidiennes ;
- **Qualité** active le modèle choisi pour les demandes exigeantes ;
- **Local** active Ollama et garantit que rien ne sort de la machine.

Le panneau interroge `/v1/models` avec la clé locale et affiche si chaque modèle
du catalogue est réellement autorisé pour le projet API. Le changement prend
effet au tour vocal suivant, sans redémarrer Jarvis.

Modèles proposés :

| Modèle | Usage conseillé | Outils | Vision |
|---|---|---|---|
| `gpt-5.6-luna` | très économique / rapide | oui | oui |
| `gpt-5.6-terra` | quotidien, meilleur équilibre | oui | oui |
| `gpt-5.6-sol` | qualité professionnelle | oui | oui |
| `gpt-6-astra` | raisonnement et tâches complexes | oui | oui |

## Ce qui a été migré

- boucle vocale principale et appels d'outils ;
- captures d'écran et vision ;
- assistant navigateur et réservations ;
- indexation du hub de contenu ;
- conversations téléphoniques ;
- comptage des tokens et estimation du coût dans le panneau État.

## Claude / Anthropic

Claude/Anthropic est une **alternative cloud prise en charge** : choisir
`cloud.fournisseur: anthropic`, puis renseigner `anthropic.cle`,
`anthropic.modele` et `anthropic.modele_qualite` dans le fichier local.

## Voix ElevenLabs

Le LLM et la voix sont désormais deux choix séparés. Dans l'onglet **Réglages**,
choisis `ElevenLabs`, `Piper`, `Kokoro`, `Windows` ou `Auto`, puis sélectionne une
voix du compte ElevenLabs et clique **Tester la voix**.

Le mode `local` garde sa promesse de confidentialité : si ElevenLabs est choisi,
Jarvis force tout de même un moteur local. En mode hybride/qualité, `Auto` choisit
ElevenLabs quand une clé valide est configurée.

## Dépannage

- **Clé absente** : ajoute `openai.cle`, puis recharge le panneau.
- **Modèle non autorisé** : choisis un modèle marqué autorisé ou vérifie le projet
  et le niveau de facturation API.
- **401** : clé invalide/révoquée ou mauvais projet.
- **429** : limite de débit ou solde API insuffisant.
- **ElevenLabs retombe sur Windows** : vérifie le badge de connexion dans
  Réglages, sélectionne `ElevenLabs`, puis teste la voix.
