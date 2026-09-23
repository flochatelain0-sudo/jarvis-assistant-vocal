# ZOEY_OS™ console

Reproduction de l'interface ZOEY_OS (console IA) en **React + TypeScript + Vite
+ Tailwind + Framer Motion**, compilée en un **seul fichier** :

```bash
npm install
npm run build     # tsc --noEmit puis vite build
node scripts/emballer.mjs   # copie dist/index.html -> ../web/console.html
```

- `npm run dev` : développement sur http://localhost:5173
- Le build final est **inline** (JS + CSS dans le HTML, aucune dépendance
  externe) et remplace `web/console.html`, servi par la route `/console` de
  Jarvis (`core/operator.py`, garde locale uniquement).
- Le chat est branché sur les **vrais endpoints** de l'Operator
  (`/api/operator/message`, `/api/operator/reponse/{id}`…) avec repli
  simulé si l'API ne répond pas (développement hors Jarvis).
