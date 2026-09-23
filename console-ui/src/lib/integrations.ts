import type { LucideIcon } from 'lucide-react'
import { Mail, Calendar, Github } from 'lucide-react'

export type IntegrationId = 'gmail' | 'gcal' | 'github'

export interface Integration {
  id: IntegrationId
  nom: string
  description: string
  icone: LucideIcon
}

export const INTEGRATIONS: Record<IntegrationId, Integration> = {
  gmail: {
    id: 'gmail',
    nom: 'GMAIL',
    description: 'Connect Gmail so Zoey can help organize your inbox.',
    icone: Mail,
  },
  gcal: {
    id: 'gcal',
    nom: 'GOOGLE CALENDAR',
    description: 'Connect Google Calendar so Zoey can organize your schedule.',
    icone: Calendar,
  },
  github: {
    id: 'github',
    nom: 'GITHUB',
    description: 'Connect GitHub so Zoey can manage your project.',
    icone: Github,
  },
}
