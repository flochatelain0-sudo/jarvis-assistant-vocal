import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import TopBar from '../components/TopBar'
import ConsoleSidebar from '../components/ConsoleSidebar'
import MainWorkspace from '../components/MainWorkspace'
import type { EtatOrbe } from '../components/ParticleOrb'
import ChatPanel from '../components/ChatPanel'
import ConnectionModal from '../components/ConnectionModal'
import ButModal from '../components/ButModal'
import IntegrationsPanel from '../components/IntegrationsPanel'
import type { ModeCentre } from '../components/WorkspaceControls'
import type { IntegrationId } from '../lib/integrations'
import { useTheme } from '../lib/theme'
import {
  api,
  type EtatOperator,
  type ModeGlobal,
  type But,
  type Automation,
  type IntegrationEtat,
} from '../lib/api'
import { useReconnaissanceVocale } from '../hooks/useReconnaissanceVocale'

export default function App() {
  const { theme, basculer: basculerTheme } = useTheme()
  const [consoleOuverte, setConsoleOuverte] = useState(true)
  const [chatOuvert, setChatOuvert] = useState(true)
  const [ecoute, setEcoute] = useState(true)
  const [mode, setMode] = useState<ModeCentre>('chat')
  const [page, setPage] = useState(0)
  const [buts, setButs] = useState<But[]>([])
  const [automations, setAutomations] = useState<Automation[]>([])
  const [integrations, setIntegrations] = useState<Record<string, IntegrationEtat>>({})
  const [connectes, setConnectes] = useState<Set<IntegrationId>>(new Set())
  const [aConnecter, setAConnecter] = useState<IntegrationId | null>(null)
  const [etapesFaites, setEtapesFaites] = useState<Set<number>>(new Set())
  const [recherche, setRecherche] = useState('')
  const [pageIntegrations, setPageIntegrations] = useState(false)
  const [modalButOuverte, setModalButOuverte] = useState(false)
  const oauthResultat = useMemo(() => {
    const p = new URLSearchParams(window.location.search).get('oauth')
    return p
  }, [])
  const [etat, setEtat] = useState<EtatOperator | null>(null)
  const [modeGlobal, setModeGlobal] = useState<ModeGlobal>('manual')
  const [transcription, setTranscription] = useState('')
  // Micro reel du navigateur : la transcription part dans le chat de Jarvis
  // (POST /api/operator/message) ; le backend prononce deja la reponse.
  const transcrire = useCallback(async (texte: string) => {
    setTranscription(texte)
    await api.envoyer(texte)
    setTimeout(() => setTranscription(''), 4000)
  }, [])
  const reco = useReconnaissanceVocale(transcrire)
  // Barre espace : push-to-talk direct (appui = ecoute, relache = envoi).
  // Ignore la touche quand on tape dans un champ de saisie ou la recherche.
  const espaceRef = useRef(false)
  useEffect(() => {
    const surAppui = (e: KeyboardEvent) => {
      const cible = e.target as HTMLElement | null
      if (
        cible &&
        (cible.tagName === 'INPUT' ||
          cible.tagName === 'TEXTAREA' ||
          cible.isContentEditable)
      )
        return
      if (e.code !== 'Space') return
      e.preventDefault()
      if (espaceRef.current) return
      espaceRef.current = true
      reco.demarrer()
    }
    const surRelache = (e: KeyboardEvent) => {
      if (e.code !== 'Space') return
      espaceRef.current = false
      reco.arreter()
    }
    window.addEventListener('keydown', surAppui)
    window.addEventListener('keyup', surRelache)
    return () => {
      window.removeEventListener('keydown', surAppui)
      window.removeEventListener('keyup', surRelache)
    }
  }, [reco])

  // le vrai pouls de Jarvis : etat de vie + journal + buts + integrations,
  // poll toutes les 5 s — TOUT vient de l'API, rien n'est simule.
  useEffect(() => {
    let vivant = true
    const maj = async () => {
      const e = await api.etat()
      if (vivant && e && e.vie) {
        setEtat(e)
        if (e.mode) setModeGlobal(e.mode)
        if (e.integrations) {
          setIntegrations(e.integrations)
          setConnectes(
            new Set(
              Object.values(e.integrations)
                .filter((i) => i.connecte)
                .map((i) => i.id as IntegrationId),
            ),
          )
        }
        if (e.buts) setButs(e.buts)
      }
    }
    maj()
    const t = setInterval(maj, 5000)
    return () => {
      vivant = false
      clearInterval(t)
    }
  }, [])

  // automations : le vrai planificateur (data/automations.json)
  useEffect(() => {
    let vivant = true
    const maj = async () => {
      const a = await api.automations()
      if (vivant && a) setAutomations(a.automations)
    }
    maj()
    const t = setInterval(maj, 5000)
    return () => {
      vivant = false
      clearInterval(t)
    }
  }, [])

  const changerMode = async (m: ModeGlobal) => {
    if (m === modeGlobal) return
    setModeGlobal(m)
    const confirme = await api.changerMode(m)
    if (confirme) setModeGlobal(confirme)
  }

  const connecter = (id: IntegrationId) => {
    setConnectes((p) => new Set(p).add(id))
    setAConnecter(null)
  }

  const ajouterBut = () => {
    setModalButOuverte(true)
  }

  const creerBut = (titre: string) => {
    api.butAjouter(titre).then((but) => {
      if (but) setButs((p) => [...p, but])
    })
  }

  const supprimerBut = (id: string) => {
    api.butSupprimer(id).then((ok) => {
      if (ok) setButs((p) => p.filter((b) => b.id !== id))
    })
  }

  const ouvrirEtape = (i: number) => {
    setEtapesFaites((p) => new Set(p).add(i))
    if (i === 1) {
      setConsoleOuverte(true)
      setMode('chat')
    } else if (i === 2) {
      setMode('configurer')
    } else if (i === 3) {
      setChatOuvert(true)
    } else {
      setMode('console')
    }
  }

  const niveauMicro = etat?.vie?.niveau ?? (ecoute ? 0.14 : 0)
  const journal = etat?.journal ?? []
  const vie = etat?.vie ?? { etat: 'veille', modele: '', routage: '' }

  return (
    <div className="flex h-full w-full flex-col pt-[60px]">
      <TopBar
        onOuvrirRecherche={() => setRecherche(' ')}
        mode={modeGlobal}
        onMode={changerMode}
        theme={theme}
        onTheme={basculerTheme}
      />

      {pageIntegrations && (
        <IntegrationsPanel
          onFermer={() => setPageIntegrations(false)}
          oauthResultat={oauthResultat}
        />
      )}

      {recherche !== '' && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[14vh]"
          style={{ background: 'var(--overlay)', backdropFilter: 'blur(6px)' }}
          onClick={() => setRecherche('')}
        >
          <div
            className="flex w-[460px] items-center gap-3 rounded-xl border px-4 py-3"
            style={{ background: 'var(--modal)', borderColor: 'var(--border-orange)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <Search size={15} className="text-orange" />
            <input
              autoFocus
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setRecherche('')}
              placeholder="Rechercher un objectif, un client, un mail…"
              className="flex-1 bg-transparent text-[14px] text-[var(--text)] outline-none placeholder:text-[var(--placeholder)]"
            />
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* gauche : console */}
        <div
          className="transition-all duration-300"
          style={{
            width: consoleOuverte ? 'clamp(230px, 25vw, 340px)' : 0,
            overflow: 'hidden',
          }}
        >
          <ConsoleSidebar
            buts={buts}
            automations={automations}
            integrations={integrations}
            connectes={connectes}
            onConnecter={(id) => setAConnecter(id as IntegrationId)}
            onAjouterBut={ajouterBut}
            onSupprimerBut={supprimerBut}
            onOuvrirEtape={ouvrirEtape}
            etapesFaites={etapesFaites}
            ouverte={consoleOuverte}
            onFermer={() => setConsoleOuverte(false)}
          />
        </div>

        {/* centre : orbe + controles */}
        <MainWorkspace
          mode={mode}
          onMode={setMode}
          ecoute={ecoute}
          onEcoute={() => {
            setEcoute((e) => !e)
            reco.basculer()
          }}
          niveau={niveauMicro}
          page={page}
          onPage={setPage}
          journal={journal}
          actions24h={etat?.kpis?.actions_24h ?? 0}
          enAttente={etat?.kpis?.en_attente ?? 0}
          vie={vie}
          etatOrbe={vie.etat as EtatOrbe}
          connectes={connectes}
          onConnecter={setAConnecter}
          orbMobile={false}
          reco={reco}
          transcription={transcription}
        />

        {/* droite : chat Jarvis */}
        <div
          className="transition-all duration-300"
          style={{ width: chatOuvert ? 'clamp(270px, 28vw, 400px)' : 0, overflow: 'hidden' }}
        >
          <ChatPanel
            ouverte={chatOuvert}
            onOuvrir={() => setChatOuvert(true)}
            onFermer={() => setChatOuvert(false)}
            onNouveauBut={() => setModalButOuverte(true)}
            journal={journal}
            enAttente={etat?.kpis?.en_attente ?? 0}
            nbButs={buts.length}
          />
        </div>
      </div>

      {!consoleOuverte && (
        <button
          onClick={() => setConsoleOuverte(true)}
          className="label-tech fixed left-4 z-30 rounded-full border px-3.5 py-1.5 text-[10px] text-[var(--dim)] transition hover:border-orange/60"
          style={{ top: 72, background: 'var(--panel-glass-strong)', borderColor: 'var(--border-orange)' }}
        >
          CONSOLE
        </button>
      )}

      <ConnectionModal
        id={aConnecter}
        connectes={connectes}
        onAnnuler={() => setAConnecter(null)}
        onConnecter={connecter}
      />
      <ButModal
        ouverte={modalButOuverte}
        onFermer={() => setModalButOuverte(false)}
        onCreer={creerBut}
      />
    </div>
  )
}
