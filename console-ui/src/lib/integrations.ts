import type { LucideIcon } from 'lucide-react'
import { Mail, Calendar, Github, Megaphone, Palette, ShoppingBag, Globe, MonitorSmartphone, Mic } from 'lucide-react'

export type IntegrationId =
  | 'gmail'
  | 'gcal'
  | 'github'
  | 'mailchimp'
  | 'canva'
  | 'shopify'
  | 'navigateur'
  | 'pc'
  | 'voix'

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
    description: 'Connect Gmail so Jarvis can help organize your inbox. Add mail.adresse (+ mot de passe d\u2019application ou OAuth) in config.yaml.',
    icone: Mail,
  },
  gcal: {
    id: 'gcal',
    nom: 'GOOGLE CALENDAR',
    description: 'Connect Google Calendar so Jarvis can organize your schedule. Run scripts/google_login.py agenda.',
    icone: Calendar,
  },
  github: {
    id: 'github',
    nom: 'GITHUB',
    description: 'Connect GitHub so Jarvis can manage code and deployments. Not yet integrated — Jarvis can use browser tools meanwhile.',
    icone: Github,
  },
  mailchimp: {
    id: 'mailchimp',
    nom: 'MAILCHIMP',
    description: 'Connect Mailchimp so Jarvis can launch and track campaigns. Not yet integrated.',
    icone: Megaphone,
  },
  canva: {
    id: 'canva',
    nom: 'CANVA',
    description: 'Connect Canva so Jarvis can create campaign visuals. Not yet integrated.',
    icone: Palette,
  },
  shopify: {
    id: 'shopify',
    nom: 'SHOPIFY',
    description: 'Connect Shopify so Jarvis can analyze products and pricing. Not yet integrated.',
    icone: ShoppingBag,
  },
  navigateur: {
    id: 'navigateur',
    nom: 'BROWSER ACCESS',
    description: 'Access the browser so Jarvis can research trends and publish content. Enabled in config.yaml (navigateur.actif).',
    icone: Globe,
  },
  pc: {
    id: 'pc',
    nom: 'LOCAL MACHINE',
    description: 'Access this computer to run builds and deploy tools. Controlled by astra_pc.actif — approvals arrive in chat.',
    icone: MonitorSmartphone,
  },
  voix: {
    id: 'voix',
    nom: 'VOICE',
    description: 'Voice input and output for Jarvis.',
    icone: Mic,
  },
}
