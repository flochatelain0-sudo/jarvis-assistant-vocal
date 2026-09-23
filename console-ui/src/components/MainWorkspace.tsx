import { useMemo } from 'react'
import ParticleOrb, { type EtatOrbe } from './ParticleOrb'
import ListeningIndicator from './ListeningIndicator'
import WorkspaceControls, { type ModeCentre } from './WorkspaceControls'
import ZoeyBranding from './ZoeyBranding'
import ConsolePanel from './ConsolePanel'
import ConfigurationPanel from './ConfigurationPanel'
import BrainPanel from './BrainPanel'
import IntegrationsPanel from './IntegrationsPanel'
import type { IntegrationId } from '../lib/integrations'

interface Props {
  mode: ModeCentre
  onMode: (mode: Exclude<ModeCentre, null>) => void
  ecoute: boolean
  onEcoute: () => void
  niveau: number
  page: number
  onPage: (p: number) => void
  journal: { ts: number; categorie: string; titre: string }[]
  actions24h: number
  enAttente: number
  vie: { etat: string; modele: string; routage: string }
  etatOrbe: EtatOrbe
  connectes: Set<IntegrationId>
  onConnecter: (id: IntegrationId) => void
  orbMobile: boolean
}

export default function MainWorkspace(props: Props) {
  const { mode, onMode, ecoute, onEcoute, niveau, page, onPage, orbMobile, etatOrbe } = props
  const tailleOrbe = useMemo(() => (orbMobile ? 300 : 430), [orbMobile])

  return (
    <main className="relative flex flex-1 flex-col items-center justify-center overflow-hidden">
      {/* orbe seul au fond */}
      <ParticleOrb etat={etatOrbe} niveau={niveau} taille={tailleOrbe} />

      {/* micro discret en haut, cliquable meme panneau ouvert */}
      <div className="absolute inset-x-0 top-6 z-30 flex justify-center">
        <ListeningIndicator actif={ecoute} onBasculer={onEcoute} />
      </div>

      {/* branding sobre en bas */}
      <div className="absolute inset-x-0 bottom-8 z-30 flex justify-center">
        <ZoeyBranding page={page} nbPages={1} onPage={onPage} />
      </div>

      {/* controles en icones, flottants discrets en bas a droite */}
      <div className="absolute bottom-5 right-5 z-30">
        <WorkspaceControls
          mode={mode}
          onChoisir={(m) => onMode(mode === m ? 'chat' : m)}
        />
      </div>

      {mode === 'console' && (
        <ConsolePanel
          onFermer={() => onMode('chat')}
          journal={props.journal}
          actions24h={props.actions24h}
          enAttente={props.enAttente}
          vie={props.vie}
        />
      )}
      {mode === 'configurer' && (
        <ConfigurationPanel
          onFermer={() => onMode('chat')}
          connectes={props.connectes}
          onConnecter={props.onConnecter}
        />
      )}
      {mode === 'brain' && <BrainPanel onFermer={() => onMode('chat')} />}
      {mode === 'integrations' && (
        <IntegrationsPanel onFermer={() => onMode('chat')} />
      )}
    </main>
  )
}

export type { ModeCentre }
