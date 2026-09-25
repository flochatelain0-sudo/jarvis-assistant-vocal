# Garde-fous d'entrée (scan du contenu externe avant le LLM)

Jarvis avale beaucoup de contenu externe : pages web (navigateur assistant,
réservation Playwright), mails Gmail, messages LinkedIn, Instagram, captures
d'écran. Tout cela entre dans l'historique du modèle — donc potentiellement
dans un prompt cloud.

Le module `core/garde_fous.py` est la **barrière d'entrée**, inspirée du
pipeline de sécurité d'[OpenJarvis](https://github.com/open-jarvis/OpenJarvis)
(`SecretScanner`, `PIIScanner`, `InjectionScanner`, modes WARN / REDACT /
BLOCK), adapté à la philosophie de ce projet : stdlib uniquement, aucun appel
réseau, jamais de crash.

## Ce qui est détecté

| Famille | Exemples | Sévérité |
|---|---|---|
| Secrets | clés OpenAI (`sk-…`), Anthropic (`sk-ant-…`), AWS (`AKIA…`), tokens GitHub/Slack/Stripe, clés Google, clés privées, chaînes de connexion, mots de passe en clair | critique / élevée |
| PII | adresses mail, cartes bancaires (Visa/Mastercard/Amex), SSN (US), téléphones (US/FR), IBAN, IPv4 publiques | critique / moyenne |
| Injection de prompt | « ignore all previous instructions », « you are now… », « reveal your system prompt », appels de code cachés | élevée |

## Les trois modes (`securite.garde_fous_entree` dans `config.yaml`)

- **`observer`** (défaut) : ne modifie rien, journalise chaque détection dans
  l'Operator (catégorie `securite`). Mode de découverte : tu vois ce que le
  scanner attrape sans rien casser.
- **`caviarder`** : remplace secrets et PII par des marqueurs
  (`[cle OpenAI:caviarde]`, `[adresse mail:caviarde]`…) avant l'entrée dans
  le modèle, et journalise.
- **`bloquer`** : refuse le texte (secret/PII à risque élevé ou injection
  avérée) — le résultat d'outil devient un avertissement pour le modèle ;
  journalise avec `resultat=bloque`.

L'injection de prompt est toujours signalée au journal ; en mode `bloquer`
seule, elle coupe le texte.

## Où ça s'applique

- **Résultats d'outils** : chaque `tool_result` texte passe par
  `garde_fous.verifier()` avant d'entrer dans l'historique (boucle principale
  `jarvis14.py` et satellites `core/satellite.py`). Les captures d'écran
  (blocs image) ne sont pas concernées.
- **Historique utilisateur** : `garde_fous.proteger_historique()` est
  disponible pour caviarder en masse les messages `role=user` externes.

La sortie reste couverte par `core/confidentialite.py` (`caviarder` /
`filtrer`), qui masque les motifs sensibles **avant la voix** — par exemple
quand Jarvis lit le résultat d'une délégation à Hermes. Entrée et sortie ont
chacune leur barrière.

## Limites assumées

Regex stdlib sur motifs évidents : ce n'est pas un pare-feu contre un
adversaire sophistiqué. Un secret reformulé, une PII hors motif reste
invisible pour le scanner. La doctrine du projet reste la vraie protection :
clés uniquement dans `config.yaml`, outils sensibles à confirmation (N2/N3),
MCP en liste blanche.

## Tests

```bash
uv run pytest tests/test_garde_fous.py -v
```

17 tests : détection par famille, caviardage, trois modes, protection
d'historique, journalisation sans jamais écrire le secret lui-même, et
non-crash en erreur interne.
