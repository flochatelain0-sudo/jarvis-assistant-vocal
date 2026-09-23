import type { IntegrationId } from '../lib/integrations'

export interface But {
  id: string
  titre: string
  statut: 'JUST SET' | 'IN PROGRESS'
  requis: { id: IntegrationId; texte: string }[]
}

export const BUTS_INITIAUX: But[] = [
  {
    id: 'b1',
    titre: 'Get my inbox and calendar u…',
    statut: 'JUST SET',
    requis: [
      { id: 'gmail', texte: 'Connect Gmail so I can help tam…' },
      { id: 'gcal', texte: 'Connect Google Calendar to org…' },
    ],
  },
  {
    id: 'b2',
    titre: 'Ship my current project to pr…',
    statut: 'JUST SET',
    requis: [
      { id: 'github', texte: 'Connect GitHub so I can manage…' },
    ],
  },
]

export const ETAPES_DEMARRAGE = [
  'Take the tour',
  'Connect your platforms and tools',
  'Put something on autopilot',
  'Watch Zoey work',
]

export const CREDITS_INITIAL = 994
