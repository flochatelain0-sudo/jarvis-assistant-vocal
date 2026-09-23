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

export interface IntegrationEtat {
  id: string
  nom: string
  connecte: boolean
  detail: string
}

export interface But {
  id: string
  titre: string
  statut: 'JUST SET' | 'IN PROGRESS' | 'DONE'
  requis: { id: string; connecte: boolean }[]
}

export interface Automation {
  id: string
  nom: string
  moment: string
  action: string
  jours: string[]
  active: boolean
  derniere: number
  prochaine: number
}

export interface DocumentConnaissance {
  id: number
  titre: string
  source: string
  ts: number
  taille: number
}

export type IntegrationStatut = 'connected' | 'available' | 'setup_required'

export interface IntegrationDef {
  id: string
  name: string
  slug: string
  description: string
  category: string
  capabilities: string[]
  scopes: string[]
  authType: string
  enabled: boolean
  requiresOAuth: boolean
  documentationUrl: string
  connected: boolean
  status: IntegrationStatut
}

export interface CatalogueIntegrations {
  integrations: IntegrationDef[]
  categories: string[]
  connectedCount: number
}

export interface ConnexionIntegration {
  provider: string
  providerAccountId: string
  scopes: string
  connectedAt: number
  expiresAt: number
}

export interface Brain {
  preferences: { cle: string; contenu: string }[]
  people: { cle: string; contenu: string }[]
  projects: { cle: string; contenu: string }[]
  facts: { contenu: string }[]
}

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
  integrations?: Record<string, IntegrationEtat>
  buts?: But[]
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
    json<{
      messages: {
        role: 'vous' | 'jarvis'
        type?: string
        texte: string
        ts: number
        categories?: {
          titre: string
          icone: string
          mails: { expediteur: string; objet: string; detail: string; action: string }[]
        }[]
        categorie?: string
        detail?: string
        resultat?: string
      }[]
    }>('/api/operator/conversation'),

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

  brain: () => json<Brain>('/api/operator/brain'),

  automations: () => json<{ automations: Automation[] }>('/api/operator/automations'),

  knowledge: () =>
    json<{ documents: DocumentConnaissance[] }>('/api/operator/knowledge'),

  knowledgeAjouter: async (titre: string, contenu: string): Promise<boolean> => {
    const r = await json<{ ok: boolean }>('/api/operator/knowledge', {
      method: 'POST',
      body: JSON.stringify({ titre, contenu }),
    })
    return Boolean(r && r.ok)
  },

  buts: () => json<{ buts: But[] }>('/api/operator/buts'),

  butAjouter: async (titre: string): Promise<But | null> => {
    const r = await json<{ ok: boolean; but: But }>('/api/operator/buts', {
      method: 'POST',
      body: JSON.stringify({ titre }),
    })
    return r && r.ok ? r.but : null
  },

  butSupprimer: async (id: string): Promise<boolean> => {
    const r = await json<{ ok: boolean }>(`/api/operator/buts/${id}`, {
      method: 'DELETE',
    })
    return Boolean(r && r.ok)
  },

  // Page INTEGRATIONS : catalogue statique + etat REEL cote serveur.
  catalogueIntegrations: () => json<CatalogueIntegrations>('/api/integrations'),

  integrationsConnectees: () =>
    json<{ connected: ConnexionIntegration[] }>('/api/integrations/connected'),

  statutIntegration: (provider: string) =>
    json<{ ok: boolean; connected: boolean; connection: ConnexionIntegration | null; enabled: boolean; setupRequired: boolean }>(
      `/api/integrations/${provider}/status`,
    ),

  connecterIntegration: async (provider: string): Promise<{ ok: boolean; authorizationUrl?: string; message?: string }> =>
    json('/api/integrations/' + provider + '/connect', { method: 'POST' }) as Promise<{ ok: boolean; authorizationUrl?: string; message?: string }>,

  deconnecterIntegration: async (provider: string): Promise<{ ok: boolean; message?: string }> =>
    json(`/api/integrations/${provider}/disconnect`, {
      method: 'POST',
    }) as Promise<{ ok: boolean; message?: string }>,
}
