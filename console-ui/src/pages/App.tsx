import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import TopBar from '../components/TopBar'
import ConsoleSidebar from '../components/ConsoleSidebar'
import MainWorkspace from '../components/MainWorkspace'
import ChatPanel from '../components/ChatPanel'
import ConnectionModal from '../components/ConnectionModal'
import type { ModeCentre } from '../components/WorkspaceControls'
import type { But } from '../data/etat-initial'
import { BUTS_INITIAUX, CREDITS_INITIAL } from '../data/etat-initial'
import type { IntegrationId } from '../lib/integrations'
import { api, type EtatOperator } from '../lib/api'

export default function App() {
  const [consoleOuverte, setConsoleOuverte] = useState(true)
  const [chatOuvert, setChatOuvert] = useState(true)
  const [ecoute, setEcoute] = useState(true)
  const [mode, setMode] = useState<ModeCentre>('chat')
  const [page, setPage] = useState(0)
  const [credits] = useState(CREDITS_INITIAL)
  const [buts, setButs] = useState<But[]>(BUTS_INITIAUX)
  const [connectes, setConnectes] = useState<Set<IntegrationId>>(new Set())
  const [aConnecter, setAConnecter] = useState<IntegrationId | null>(null)
  const [etapesFaites, setEtapesFaites] = useState<Set<number>>(new Set())
  const [recherche, setRecherche] = useState('')
  const [etat, setEtat] = useState<EtatOperator | null>(null)

  // le vrai pouls de Jarvis : etat de vie + journal, poll toutes les 5 s
  useEffect(() => {
    let vivant = true
    const maj = async () => {
      const e = await api.etat()
      if (vivant && e && e.vie) setEtat(e)
    }
    maj()
    const t = setInterval(maj, 5000)
    return () => {
      vivant = false
      clearInterval(t)
    }
  }, [])

  const connecter = (id: IntegrationId) => {
    setConnectes((p) => new Set(p).add(id))
    setAConnecter(null)
  }

  const ajouterBut = () => {
    setButs((p) => [
      ...p,
      {
        id: `b${p.length + 1}`,
        titre: 'New goal — describe what you want…',
        statut: 'JUST SET',
        requis: [],
      },
    ])
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
      <TopBar onOuvrirRecherche={() => setRecherche(' ')} />

      {recherche !== '' && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[14vh]"
          style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(6px)' }}
          onClick={() => setRecherche('')}
        >
          <div
            className="flex w-[460px] items-center gap-3 rounded-xl border px-4 py-3"
            style={{ background: '#0d0d0d', borderColor: 'var(--border-orange)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <Search size={15} className="text-orange" />
            <input
              autoFocus
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setRecherche('')}
              placeholder="Rechercher un objectif, un client, un mail…"
              className="flex-1 bg-transparent text-[14px] text-[#f5f5f5] outline-none placeholder:text-[#555]"
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
            connectes={connectes}
            onConnecter={setAConnecter}
            onAjouterBut={ajouterBut}
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
          onEcoute={() => setEcoute((e) => !e)}
          niveau={niveauMicro}
          page={page}
          onPage={setPage}
          journal={journal}
          actions24h={etat?.kpis?.actions_24h ?? 0}
          enAttente={etat?.kpis?.en_attente ?? 0}
          vie={vie}
          connectes={connectes}
          onConnecter={setAConnecter}
          orbMobile={false}
          credits={credits}
        />

        {/* droite : chat Zoey */}
        <div
          className="transition-all duration-300"
          style={{ width: chatOuvert ? 'clamp(270px, 28vw, 400px)' : 0, overflow: 'hidden' }}
        >
          <ChatPanel
            ouverte={chatOuvert}
            onOuvrir={() => setChatOuvert(true)}
            onFermer={() => setChatOuvert(false)}
            journal={journal}
            enAttente={etat?.kpis?.en_attente ?? 0}
          />
        </div>
      </div>

      {!consoleOuverte && (
        <button
          onClick={() => setConsoleOuverte(true)}
          className="label-tech fixed left-4 z-30 rounded-full border px-3.5 py-1.5 text-[10px] text-[#c7c7c7] transition hover:border-orange/60"
          style={{ top: 72, background: 'rgba(8,8,8,0.85)', borderColor: 'var(--border-orange)' }}
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
    </div>
  )
}
