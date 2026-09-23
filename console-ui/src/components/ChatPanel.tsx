import { useEffect, useRef, useState } from 'react'
import { Plus, SendHorizontal, RotateCcw, ExternalLink, X, AudioLines } from 'lucide-react'
import { api } from '../lib/api'

export interface MailRendu {
  expediteur: string
  objet: string
  detail: string
  action: string
  brouillon?: string
}

export interface CategorieMails {
  titre: string
  icone: string
  mails: MailRendu[]
}

export interface ActionVue {
  categorie: string
  detail: string
  resultat: string
}

export interface CarteBriefing {
  client: string
  rdv?: string
  champs: { titre: string; valeur: string }[]
}

export interface MessageChat {
  id: number
  role: 'vous' | 'zoey'
  texte: string
  ts: number
  tsServeur?: number
  carteMails?: CategorieMails[]
  carteBriefing?: CarteBriefing
  action?: ActionVue
}

interface Props {
  ouverte: boolean
  onOuvrir: () => void
  onFermer: () => void
  onNouveauBut: () => void
  journal: { ts: number; categorie: string; titre: string }[]
  enAttente: number
}

const MESSAGE_ACCUEIL: MessageChat[] = [
  {
    id: 1,
    role: 'zoey',
    texte:
      "Hey — I'm Jarvis. I keep an eye on your inbox, calendar and projects so you don't have to. What should we get on top of first?",
    ts: Date.now() / 1000 - 90,
  },
  {
    id: 2,
    role: 'zoey',
    texte:
      'I set two goals for us: getting your inbox and calendar under control, and shipping your current project. Connect the platforms below and I\u2019ll take it from there.',
    ts: Date.now() / 1000 - 60,
  },
]

let compteur = 100

const messageAccueil = (): MessageChat[] =>
  MESSAGE_ACCUEIL.map((m) => ({ ...m, ts: Date.now() / 1000 - 90 }))
const maintenant = () => Date.now() / 1000

async function attendreReponse(texte: string): Promise<string | null> {
  // le vrai pipeline Jarvis depose la reponse dans la conversation serveur ;
  // le poll l'affichera. On ne l'ajoute PAS ici : plus de double affichage.
  const id = await api.envoyer(texte)
  if (id !== null) {
    for (let i = 0; i < 240; i++) {
      await new Promise((r) => setTimeout(r, 500))
      const rep = await api.reponse(id)
      if (rep !== null) return rep
    }
    return null
  }
  // 2) repli simule (npm run dev hors Jarvis)
  await new Promise((r) => setTimeout(r, 900 + Math.random() * 900))
  const reponses = [
    "On it. I'll watch your inbox and nudge you only when something actually needs you.",
    'Noted. Want me to put that on autopilot, or keep it manual for now?',
    "Done — I've queued it. I'll report back here and by voice when there's movement.",
    "I can do that once my platform is connected. Hit CONNECT in the console on the left.",
  ]
  return reponses[Math.floor(Math.random() * reponses.length)]
}

export default function ChatPanel({ ouverte, onOuvrir, onFermer, onNouveauBut, journal, enAttente }: Props) {
  const [messages, setMessages] = useState<MessageChat[]>(messageAccueil())
  const [saisie, setSaisie] = useState('')
  const [reflechir, setReflechir] = useState(false)
  const basRef = useRef<HTMLDivElement>(null)

  // rejoue la conversation existante du vrai Jarvis, puis la suit en direct :
  // actions executees, cartes de compte rendu et reponses arrivent sans
  // recharger, meme panneau ouvert (poll toutes les 3 s, meme dedup).
  useEffect(() => {
    if (!ouverte) return
    let vivant = true
    const maj = () =>
      api.conversation().then((c) => {
        if (!vivant || !c || !c.messages || !c.messages.length) return
        setMessages((prec) => {
          // Deduplication sur le ts SERVEUR : chaque message du backend est
          // affiche une seule fois, meme si deux messages identiques se
          // suivent (« oui » deux fois de suite, par exemple).
          const vus = new Set(prec.map((m) => m.tsServeur).filter(Boolean))
          const ajoutes: MessageChat[] = []
          for (const m of c.messages!) {
            if (m.role !== 'vous' && m.role !== 'jarvis') continue
            const role = (m.role === 'vous' ? 'vous' : 'zoey') as 'vous' | 'zoey'
            const tsServeur = m.ts || 0
            if (tsServeur && vus.has(tsServeur)) continue
            if (tsServeur) vus.add(tsServeur)
            ajoutes.push({
              id: ++compteur,
              role,
              texte: m.texte,
              ts: m.ts || maintenant(),
              tsServeur: tsServeur || undefined,
              carteMails: m.type === 'mails' ? m.categories : undefined,
              carteBriefing:
                m.type === 'briefing' && m.champs && m.champs.length
                  ? { client: m.client || m.texte, rdv: m.rdv, champs: m.champs }
                  : undefined,
              action:
                m.type === 'action'
                  ? { categorie: m.categorie || 'autre', detail: m.detail || '', resultat: m.resultat || 'ok' }
                  : undefined,
            })
          }
          return ajoutes.length ? [...prec, ...ajoutes] : prec
        })
      })
    maj()
    const t = setInterval(maj, 3000)
    return () => {
      vivant = false
      clearInterval(t)
    }
  }, [ouverte])

  useEffect(() => {
    basRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, reflechir])

  const envoyer = async () => {
    const texte = saisie.trim()
    if (!texte || reflechir) return
    setSaisie('')
    setReflechir(true)
    await attendreReponse(texte)
    setReflechir(false)
  }

  if (!ouverte) {
    return (
      <button
        onClick={onOuvrir}
        className="fixed right-4 z-30 flex h-9 items-center gap-2 rounded-full border px-3.5 transition hover:border-orange/60"
        style={{ top: 72, background: 'var(--panel-glass-strong)', borderColor: 'var(--border-orange)' }}
      >
        <AudioLines size={13} className="text-orange" />
        <span className="label-tech text-[10px] text-[var(--dim)]">JARVIS</span>
      </button>
    )
  }

  return (
    <aside
      className="flex flex-col border-l"
      style={{ background: 'var(--panel-glass)', borderColor: 'var(--border)' }}
    >
      {/* entete */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full bg-orange"
            style={{ boxShadow: '0 0 10px rgba(255,106,0,0.7)' }}
          />
          <span className="label-tech text-[var(--dim)]">JARVIS</span>
          {enAttente > 0 && (
            <span className="label-tech rounded-full border px-2 text-[8.5px] text-orange"
              style={{ borderColor: 'var(--border-orange)' }}>
              {enAttente} to confirm
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[var(--muted)]">
          <button aria-label="Réinitialiser" onClick={() => setMessages(messageAccueil())}
            className="transition hover:text-[var(--text)]"><RotateCcw size={13} /></button>
          <button aria-label="Ouvrir dans un onglet" onClick={() => window.open('/console', '_blank')}
            className="transition hover:text-[var(--text)]"><ExternalLink size={13} /></button>
          <span className="h-2 w-2 rounded-full bg-orange" style={{ boxShadow: '0 0 8px rgba(255,106,0,0.7)' }} />
          <button aria-label="Fermer" onClick={onFermer} className="transition hover:text-[var(--text)]"><X size={13} /></button>
        </div>
      </div>

      {/* conversation */}
      <div className="flex-1 overflow-y-auto px-4 pb-3">
        {messages.map((m) => (
          <div key={m.id} className="mb-4">
            {m.action ? (
              <div
                className="flex max-w-[95%] items-center gap-2.5 rounded-lg border px-3 py-2"
                style={{
                  borderColor:
                    m.action.resultat === 'erreur'
                      ? 'rgba(255,80,80,0.4)'
                      : m.action.resultat === 'en_attente'
                        ? 'rgba(255,133,0,0.4)'
                        : 'var(--border)',
                  background: 'var(--panel-glass)',
                }}
              >
                <span className="label-tech shrink-0 rounded px-1.5 py-0.5 text-[8px] text-orange/90"
                  style={{ border: '1px solid rgba(255,106,0,0.35)' }}>
                  {m.action.categorie.toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12px] text-[var(--dim)]">{m.texte}</div>
                  {m.action.detail && (
                    <div className="truncate text-[10px] text-[var(--muted)]">{m.action.detail}</div>
                  )}
                </div>
                <span
                  className="label-tech shrink-0 text-[8px]"
                  style={{
                    color:
                      m.action.resultat === 'erreur'
                        ? '#ff5050'
                        : m.action.resultat === 'en_attente'
                          ? '#ff8500'
                          : '#4ade80',
                  }}
                >
                  {m.action.resultat === 'erreur'
                    ? 'ERREUR'
                    : m.action.resultat === 'en_attente'
                      ? 'A CONFIRMER'
                      : 'OK'}
                </span>
              </div>
            ) : m.carteBriefing ? (
              <div
                className="mb-1 max-w-[95%] rounded-xl border p-3"
                style={{ borderColor: 'var(--border-orange)', background: 'rgba(14,14,14,0.9)' }}
              >
                <div className="label-tech mb-2 text-[9.5px] text-orange">
                  {m.carteBriefing.client.toUpperCase()}
                  {m.carteBriefing.rdv ? ` · ${m.carteBriefing.rdv}` : ''}
                </div>
                {m.carteBriefing.champs.map((c, i) => (
                  <div key={i} className="mb-1 flex gap-2 text-[12px] last:mb-0">
                    <span className="shrink-0 text-[var(--muted)]">{c.titre}</span>
                    <span className="text-[var(--dim)]">{c.valeur}</span>
                  </div>
                ))}
              </div>
            ) : m.carteMails ? (
              <div
                className="mb-1 max-w-[95%] rounded-xl border p-3"
                style={{ borderColor: 'var(--border-orange)', background: 'rgba(14,14,14,0.9)' }}
              >
                <div className="label-tech mb-2 flex items-center gap-2 text-[9.5px] text-orange">
                  <span>{m.texte}</span>
                </div>
                {m.carteMails.map((cat, i) => (
                  <div key={i} className="mb-2 last:mb-0">
                    <div className="label-tech mb-1 flex items-center gap-1.5 text-[9px] text-[var(--text)]">
                      <span>{cat.icone}</span>
                      <span>{cat.titre}</span>
                      <span className="text-[var(--muted)]">({cat.mails.length})</span>
                    </div>
                    <div className="overflow-hidden rounded-lg border" style={{ borderColor: 'var(--border)' }}>
                      {cat.mails.map((mail, j) => (
                        <div
                          key={j}
                          className="flex flex-col gap-0.5 px-2.5 py-1.5"
                          style={{ background: j % 2 ? 'rgba(20,20,20,0.6)' : 'rgba(8,8,8,0.6)' }}
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="truncate text-[12px] font-medium text-[var(--text)]">
                              {mail.expediteur}
                            </span>
                            <span className="label-tech shrink-0 text-[8px] text-orange/80">
                              {mail.action}
                            </span>
                          </div>
                          {mail.objet && (
                            <div className="truncate text-[11px] text-[var(--muted)]">{mail.objet}</div>
                          )}
                          {mail.detail && (
                            <div className="text-[11px] text-[var(--muted)]">{mail.detail}</div>
                          )}
                          {mail.brouillon && (
                            <div
                              className="mt-1 rounded-md border px-2 py-1"
                              style={{ borderColor: 'var(--border)', background: 'rgba(28,24,16,0.5)' }}
                            >
                              <div className="label-tech text-[8px] text-orange/80">
                                ✍️ Brouillon proposé
                              </div>
                              <div className="whitespace-pre-wrap text-[11px] text-[var(--text)]">
                                {mail.brouillon}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div
                className="max-w-[92%] text-[15px] leading-[1.65]"
                style={{ color: m.role === 'vous' ? '#f5f5f5' : '#c7c7c7' }}
              >
                {m.texte}
              </div>
            )}
            <div className="label-tech mt-1 text-[8.5px] text-[var(--placeholder)]">
              {m.role === 'zoey' ? 'JARVIS' : 'YOU'} ·{' '}
              {new Date(m.ts * 1000).toLocaleTimeString('fr-FR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
          </div>
        ))}
        {reflechir && (
          <div className="mb-4 flex items-center gap-2 text-[var(--muted)]">
            <span className="point-vert h-1.5 w-1.5 rounded-full bg-green" />
            <span className="label-tech text-[9px]">LISTENING / THINKING…</span>
          </div>
        )}
        <div ref={basRef} />
      </div>

      {/* dernieres actions (journal reel de Jarvis) */}
      {journal.length > 0 && (
        <div className="border-t px-4 py-2" style={{ borderColor: 'var(--border)' }}>
          {journal.slice(0, 2).map((j, i) => (
            <div key={i} className="truncate py-0.5 text-[11px] text-[var(--muted)]">
              <span className="text-orange/80">•</span> {j.titre}
            </div>
          ))}
        </div>
      )}

      {/* saisie */}
      <div className="p-3">
        <div
          className="flex items-center gap-2 rounded-xl border px-2 py-1.5"
          style={{ background: 'var(--panel-glass)', borderColor: 'var(--border-orange)' }}
        >
          <button
            aria-label="Nouveau but"
            title="Nouveau but"
            onClick={onNouveauBut}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-orange text-[var(--bg2)] transition hover:brightness-110"
          >
            <Plus size={14} />
          </button>
          <input
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && envoyer()}
            placeholder="Message Jarvis..."
            className="flex-1 bg-transparent text-[14px] text-[var(--text)] outline-none placeholder:text-[var(--placeholder)]"
          />
          <button
            aria-label="Envoyer"
            onClick={envoyer}
            disabled={!saisie.trim() || reflechir}
            className="shrink-0 rounded-lg p-1.5 text-orange transition enabled:hover:bg-orange/10 disabled:opacity-30"
          >
            <SendHorizontal size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
