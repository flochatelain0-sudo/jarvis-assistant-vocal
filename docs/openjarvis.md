# 🔌 Brancher OpenJarvis à Jarvis

[OpenJarvis](https://github.com/open-jarvis/OpenJarvis) (Stanford) est un framework
d'IA personnelle **local-first** : moteurs d'inférence locaux (Ollama, vLLM,
Apple Foundation Models…), agents planifiés/continus, mémoire, recherche
approfondie. Jarvis est l'assistant vocal fini. Les deux parlent MCP dans les
**deux sens** — la combinaison naturelle : Jarvis comme voix, OpenJarvis
comme raisonnement.

| Sens | Chez OpenJarvis | Chez Jarvis |
|---|---|---|
| OpenJarvis pilote la domotique (Hue, OBS, minuteurs…) | `[tools.mcp]` dans `config.toml` | [`jarvis/mcp_server.py`](../jarvis/mcp_server.py) — voir [mcp.md](mcp.md) |
| Jarvis délègue le raisonnement (recherche, mémoire, tâches planifiées) | `jarvis serve` ou son serveur MCP | `mcp_externes:` dans `config.yaml` — voir [mcp_externe.md](mcp_externe.md) |

---

## 1. OpenJarvis pilote Jarvis (domotique)

Démarre le serveur MCP de Jarvis en mode HTTP (il tourne indépendamment de
l'assistant vocal) :

```bash
./launch_mcp_server.sh        # ou : JARVIS_MCP_TRANSPORT=http uv run python -m jarvis.mcp_server
```

Le serveur écoute sur `http://127.0.0.1:8765/mcp` (streamable HTTP). Puis dans
le `config.toml` d'OpenJarvis :

```toml
[tools.mcp]
enabled = true
servers = """
[{"name": "jarvis", "url": "http://127.0.0.1:8765/mcp"}]
"""
```

Les outils exposés par Jarvis (lumieres Hue, OBS, `meteo`, `lancer_minuteur`,
`heure_et_date`, stats système…) apparaissent comme des outils natifs du
registre d'OpenJarvis. Ses agents peuvent alors les appeler — le
`scheduled-monitor` peut par exemple piloter les lumières sur calendrier.

> **Sécurité** : le transport HTTP de Jarvis n'a **pas d'authentification**,
> c'est pourquoi il n'écoute que sur la boucle locale (`mcp.host` dans
> `config.yaml`). N'expose pas ce port au réseau sans ajouter un reverse
> proxy authentifié. Les outils à confirmation exigent toujours
> `confirm: true` — un agent externe ne peut pas couper ton stream en
> silence.

Vérifié en pratique : `initialize` → `tools/list` (19 outils) →
`call_tool("heure_et_date")` répond *"Il est 4 heures 23, le mardi 22
septembre 2026."* par le pont MCP stdio puis HTTP.

## 2. Jarvis délègue à OpenJarvis (raisonnement)

Démarre le serveur MCP d'OpenJarvis (voir sa documentation — `jarvis serve`),
puis déclare-le dans `config.yaml` :

```yaml
mcp_externes:
  - nom: openjarvis
    url: "http://127.0.0.1:8000/mcp"
    sans_confirmation: []   # la recherche et la lecture mémoire sont sans risque ;
                            # ajoute ici les seuls outils en lecture seule
```

Au démarrage, Jarvis affiche le nombre d'outils découverts ; à la voix :

> « Hey Jarvis, fais une recherche approfondie sur l'efficacité des modèles
> locaux » → Jarvis transcrit, appelle l'agent `deep_research` d'OpenJarvis,
> et énonce le résultat avec ses sources par Piper.

Rappels de sécurité (voir [mcp_externe.md](mcp_externe.md)) : tout outil
distant demande confirmation vocale sauf `sans_confirmation` — c'est voulu,
car les effets d'un agent distant ne se devinent pas depuis son nom.

## 3. Aller plus loin

- **Vocabulaire** : OpenJarvis répond en anglais par défaut ; Jarvis lui
  parlera dans la langue de ses prompts système comme avec tout serveur MCP.
- **Skills** : OpenJarvis importe des skills depuis n'importe quel dépôt
  GitHub ([agentskills.io](https://agentskills.io)). Les intentions de
  routage de Jarvis (`core/routage.py`) peuvent être empaquetées de la sorte.
- **Moteur Apple Foundation Models** : OpenJarvis embarque un moteur local
  macOS 26+ (`afm`). L'abstraction fournisseur de Jarvis
  (`core/llm.py` + `core/cloud.py`) peut l'adopter sans MCP — piste pour un
  mode 100 % local sur Mac.
