# Contrôle par gestes de la main (webcam)

Piloter Jarvis d'un geste, en **temps réel** et **100 % en local**. Pensé pour être
**fiable** (petit vocabulaire de gestes tenus) et **respectueux de la vie privée**
(aucune image ne quitte jamais la machine, ni même le sous-process de tracking).

> **Doctrine — Jarvis pur (physique, temps réel).** Aucun rôle pour Hermes ici.
> Les gestes ne déclenchent que des actions **N1/N2** ; **jamais** de N3 (pas
> d'extinction, d'appel, de réservation par geste.

## Pourquoi un sous-process séparé (Python 3.11)

MediaPipe n'a **pas de wheel Python 3.13** (Jarvis tourne en 3.13). Le tracking
tourne donc dans un **venv isolé Python 3.11** (`gestes/.venv-tracker`). C'est aussi
la **frontière vie privée** : ce process est le **seul** à voir l'image ; il n'en
sort que des *labels de gestes* (`"poing"`, `"mode_fenetres"`…), envoyés à Jarvis
en **loopback** local. Bonus : process séparé = **il ne vole rien à Whisper** (CPU
ordonnancé par l'OS).

```
Webcam USB → [sous-process 3.11 : OpenCV + MediaPipe HandLandmarker + FSM anti-faux-positif]
               └─ POST http://127.0.0.1:8790/api/gestes  {geste: "poing"}   (loopback + token)
Jarvis (3.13) : core/gestes.py → mappe → action N1/N2 → feedback (bip + flash HUD)
```

## Installation

```bash
python scripts/setup_gestes.py
```

Crée le venv 3.11, installe `mediapipe`/`opencv-python`/`requests`, télécharge le
modèle `hand_landmarker.task` (~8 Mo). **Une webcam USB** est requise (pas une caméra
IP : latence rédhibitoire).

Puis, à la voix : **« Jarvis, active les gestes »** / **« coupe les gestes »**, ou
`gestes.actif: true` dans `config.yaml`, ou le **raccourci clavier** (défaut
`Ctrl+Alt+G`).

## Le vocabulaire (v2) et le mapping par défaut

Des gestes **tenus** (pas d'instantané) pour éviter les faux positifs :

| Geste | Action par défaut |
|---|---|
| **Main ouverte immobile** tenue | Pause (touche média lecture/pause) |
| **Pouce levé** tenu | Lecture/reprise (touche média lecture/pause) |
| **Poing** tenu | Coupe immédiatement le TTS et annule le mode courant |
| **2 doigts** tenus | Arme le mode **Fenêtres** |
| **3 doigts** tenus | Arme le mode **Audio** |

Chaque geste reconnu = **feedback discret** (petit bip + flash HUD) pour savoir que
c'est pris. Le mapping est **entièrement éditable** dans `config.yaml → gestes.mapping`.

### Mode Fenêtres — 2 doigts

- tiens index + majeur environ 1 seconde → overlay `🪟 Mode fenêtres` ;
- passe à la main entière ouverte et garde-la brièvement immobile ;
- swipe gauche/droite → fenêtre précédente/suivante (`Alt+Shift+Tab` / `Alt+Tab`) ;
- swipe haut/bas → défilement de la fenêtre active (`Page Up` / `Page Down`).

### Mode Audio — 3 doigts

- tiens index + majeur + annulaire environ 1 seconde → overlay `🔊 Mode audio` ;
- passe à la main entière ouverte et garde-la brièvement immobile ;
- swipe haut/bas → volume +/− ;
- swipe gauche/droite → piste précédente/suivante.

Le pouce levé ne confirme **jamais** une action N3 : il sert uniquement à la
lecture média. Une extinction, un appel ou une réservation reste soumis à la
confirmation vocale locale.

## Anti-faux-positifs (le vrai défi)

- **Gestes statiques tenus** : une pose accidentelle d'une seule image ne suffit pas.
- **Modes explicites** : aucun swipe n'agit sans 2 ou 3 doigts tenus au préalable.
- **Transition stabilisée** après la sélection : passer directement à la paume
  ouverte suffit ; sortir la main du cadre reste accepté.
- **Main hors cadre obligatoire après l'action** pour empêcher un deuxième ordre
  involontaire.
- **Une seule action par mode**, puis retour au neutre et nouvelle sélection obligatoire.
- **Expiration** du mode après `mode_duree_s` secondes (30 s par défaut).
- **Stabilisation** : la main déployée (3 ou 4 doigts visibles) doit rester presque immobile pendant
  `swipe_pret_s` (0,35 s par défaut). Le changement de pose ou le trajet d'entrée
  dans le cadre ne peut donc plus être interprété comme un swipe.
- **Déplacement minimal + axe dominant** : un mouvement diagonal ambigu est ignoré.
- **Cooldown** entre deux commandes côté tracker et côté Jarvis.

## Calibration (à l'arrivée de la webcam)

```bash
python scripts/gestes_calibrer.py
```

Affiche la caméra + les landmarks, la pose et le mode en direct. Réglages :
`t/T` maintien −/+, `c/C` cooldown −/+, `w/W` swipe horizontal −/+,
`v/V` swipe vertical −/+, `i` inverse haut/bas, `s` sauvegarde vers
`gestes/calibration.json`, `q`
quitte. Le fichier sauvegardé est rechargé à la prochaine ouverture. **Aucune
image n'est enregistrée** pendant la calibration.

## Caméra : cycle de vie & cohabitation

- **On/off** : à la voix (`controler_gestes`), au raccourci clavier, ou `gestes.actif`.
  À l'arrêt de Jarvis, la webcam est **libérée** (`atexit`).
- **Choix du périphérique** : `gestes.device` (0 = première webcam USB).
- **Statut** : `GET http://127.0.0.1:8790/api/gestes/status` → `{actif}` (repris dans
  `hermes-workspace/status-hermes.ps1` : *Tracker de gestes : UP/DOWN*).
- **Cohabitation stream** : si OBS occupe déjà la webcam physique, sélectionne une
  autre `device`, ou utilise la **caméra virtuelle OBS** comme source des gestes.
  L'ancien mapping contextuel OBS reste compatible s'il est conservé manuellement,
  mais il n'est plus le mapping v2 par défaut.
- **Indicateur** : la LED de la webcam s'allume quand la caméra est active — jamais
  de capture à ton insu.

## 🔒 Vie privée (une caméra chez soi = sujet sérieux)

- **Traitement 100 % local.** Aucune image n'est **stockée**, **loggée** ni
  **transmise**. Seules des **coordonnées de landmarks** existent en mémoire du
  sous-process, et elles ne sont **même pas écrites dans les logs**.
- Ce qui traverse vers Jarvis : **uniquement un label de geste** (une chaîne).
- La caméra n'est **JAMAIS** exposée en **MCP** ni accessible à **Hermes**
  (`controler_gestes` est `mcp_expose=False`).
- L'endpoint `/api/gestes` est **loopback + token** : un process local malveillant ne
  peut pas injecter de faux gestes sans le jeton (généré à chaque activation, connu du
  seul sous-process lancé par Jarvis).

## 🛡️ Sécurité — N1/N2 uniquement

Un geste ne peut déclencher qu'une action **sûre** (lumières, média, couper le TTS,
scènes OBS). Double garde-fou dans `core/gestes.py` :
1. Seules les actions d'une **liste blanche** (`_ACTIONS_SURES`) sont exécutables.
2. Toute action qui viserait un outil classé **N3** est **refusée** en amont
   (`_verifier_non_n3`). Impossible d'éteindre le PC, d'appeler ou de réserver d'un
   geste — même en modifiant le mapping.

## Configuration (`config.yaml → gestes`)

Voir `config.example.yaml` pour toutes les clés (device, fps, seuils, armement,
mapping, `pause_pendant_live`, `raccourci`). `gestes/calibration.json` (issu de la
calibration) **prime** sur `gestes.seuils`.
