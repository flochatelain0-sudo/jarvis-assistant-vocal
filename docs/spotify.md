# Spotify — playlist des musiques reconnues

Quand Jarvis identifie une musique (« c'est quoi cette musique ? »), il peut
l'**ajouter à une playlist Spotify** — à la voix (« ajoute-la à ma playlist ») ou
**automatiquement**. La playlist par défaut : **« Jarvis Finds »** (créée si absente).
Jarvis peut aussi lancer directement un titre ou une playlist, sans passer par
Astra : « joue *Blinding Lights* sur Spotify », « lance ma playlist Chill ».

## Mise en route (une fois)

### 1. Crée une app Spotify
1. Va sur **https://developer.spotify.com/dashboard** → *Create app*.
2. Note le **Client ID** et le **Client secret**.
3. Dans les *Settings* de l'app, ajoute l'**URI de redirection EXACTE** :
   `http://127.0.0.1:8899/callback`

### 2. `config.yaml`
```yaml
spotify:
  client_id: "ton-client-id"
  client_secret: "ton-client-secret"
  playlist: "Jarvis Finds"     # nom de la playlist cible
  auto_ajout: false            # true = ajout AUTO à chaque musique reconnue
```

### 3. Connexion
```bash
python scripts/spotify_login.py
```
Ton navigateur s'ouvre → autorise. Le **refresh_token** est sauvé dans
`logs/spotify/token.json` (gitignoré) et réutilisé ensuite. Redémarre Jarvis.

## Utilisation

- **À la voix** : après « c'est quoi cette musique ? », dis « **ajoute-la à ma
  playlist** » → l'ajoute à *Jarvis Finds* (évite les doublons).
- **Automatique** : `spotify.auto_ajout: true` → **chaque musique reconnue en direct**
  (micro ou audio système) est ajoutée en tâche de fond, sans rien dire. *(L'ajout
  auto ne s'applique PAS à l'identification d'un fichier — seulement aux découvertes
  live.)*
- Titre précis : « ajoute *Blinding Lights* de The Weeknd à ma playlist ».
- Lecture : « joue *Blinding Lights* sur Spotify », « lance ma playlist Chill ».
- Contrôles locaux : « pause », « musique suivante », « musique précédente ».

## Les outils

| Outil | Niveau | MCP | Effet |
|---|---|---|---|
| `ajouter_a_playlist` | N1 | non | ajoute la dernière musique reconnue (ou un titre donné) |
| `lire_spotify` | N1 | non | recherche et lance un titre ou une playlist |

## Sécurité / vie privée

- `client_secret` et le **refresh_token** sont des secrets : `config.yaml` et
  `logs/` sont **gitignorés**. Les droits demandés sont limités aux playlists
  (`playlist-read/modify`) et au contrôle Spotify Connect
  (`user-read/modify-playback-state`).
- Non exposé au MCP : Hermes/le réseau ne peuvent pas toucher à ta playlist.
- La lecture automatique utilise les permissions Spotify Connect
  `user-read-playback-state` et `user-modify-playback-state`. Elle nécessite un
  compte Premium et un appareil Spotify disponible. Sans cela, Jarvis ouvre le
  bon résultat dans l'application, toujours sans Astra.
- API **officielle** Spotify (contrairement à Alexa) : stable, ne « casse » pas.
