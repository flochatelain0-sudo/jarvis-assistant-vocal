// Client des vrais endpoints de l'Operator (routes LOCALES de Jarvis,
// core/operator.py). Si l'API ne repond pas (npm run dev hors Jarvis),
// le chat retombe sur un mode simule — l'interface reste utilisable.

export interface EtatVie {
  etat: 'veille' | 'ecoute' | 'reflexion' | 'parole'
  modele: string
  routage: string
  micro: boolean
  niveau: number
}

export type ModeGlobal = 'manual' | 'auto'

export interface EtatOperator {
  kpis: {
    actions_24h: number
    en_attente: number
    par_categorie: Record<string, number>
    periode_nuit: boolean
  }
  a_valider: {
    id: number
    outil: string
    niveau: string
    annonce: string
  }[]
  journal: { ts: number; categorie: string; titre: string }[]
  vie: EtatVie
  mode?: ModeGlobal
}

async function json<T>(chemin: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(chemin, {
      ...init,
      headers: { 'Content-Type': 'application/json' },
    })
    return (await r.json()) as T
  } catch {
    return null
  }
}

export const api = {
  etat: () => json<EtatOperator>('/api/operator/etat'),

  mode: () => json<{ mode: ModeGlobal }>('/api/operator/mode'),

  changerMode: async (mode: ModeGlobal): Promise<ModeGlobal | null> => {
    const r = await json<{ ok: boolean; mode: ModeGlobal }>('/api/operator/mode', {
      method: 'POST',
      body: JSON.stringify({ mode }),
    })
    return r && r.ok ? r.mode : null
  },

  conversation: () =>
    json<{ messages: { role: 'vous' | 'jarvis'; texte: string; ts: number }[] }>(
      '/api/operator/conversation',
    ),

  // Envoie une demande ecrite ; renvoie l'identifiant a poller, ou null si
  // l'API est absente (mode simule).
  envoyer: async (texte: string): Promise<number | null> => {
    const r = await json<{ ok: boolean; id: number }>('/api/operator/message', {
      method: 'POST',
      body: JSON.stringify({ texte }),
    })
    return r && r.ok ? r.id : null
  },

  reponse: async (id: number): Promise<string | null> => {
    const r = await json<{ pret: boolean; texte: string }>(
      `/api/operator/reponse/${id}`,
    )
    return r && r.pret ? r.texte : null
  },
}
