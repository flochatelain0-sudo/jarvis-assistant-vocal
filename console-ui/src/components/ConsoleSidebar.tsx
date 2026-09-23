import { useState } from 'react'
import { Activity, Target, Plus, Minus, X, ChevronRight } from 'lucide-react'
import type { But } from '../data/etat-initial'
import { ETAPES_DEMARRAGE } from '../data/etat-initial'
import { INTEGRATIONS, type IntegrationId } from '../lib/integrations'
import GettingStarted from './GettingStarted'

interface Props {
  buts: But[]
  connectes: Set<IntegrationId>
  onConnecter: (id: IntegrationId) => void
  onAjouterBut: () => void
  onOuvrirEtape: (i: number) => void
  etapesFaites: Set<number>
  ouverte: boolean
  onFermer: () => void
}

export default function ConsoleSidebar({
  buts,
  connectes,
  onConnecter,
  onAjouterBut,
  onOuvrirEtape,
  etapesFaites,
  ouverte,
  onFermer,
}: Props) {
  const [repliee, setRepliee] = useState(false)

  if (!ouverte) return null

  return (
    <aside
      className="flex flex-col overflow-y-auto border-r"
      style={{ background: 'rgba(8,8,8,0.75)', borderColor: 'var(--border)' }}
    >
      {/* entete CONSOLE */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full bg-orange"
            style={{ boxShadow: '0 0 10px rgba(255,106,0,0.7)' }}
          />
          <span className="label-tech text-[#c7c7c7]">CONSOLE</span>
        </div>
        <button
          onClick={onFermer}
          aria-label="Fermer la console"
          className="rounded p-1 text-[#777777] transition hover:text-[#f5f5f5]"
        >
          <X size={13} />
        </button>
      </div>

      {/* ACTIVITY */}
      <section className="px-4 pb-4">
        <div className="mb-3 flex items-center gap-2">
          <Activity size={11} className="text-orange" />
          <span className="label-tech text-orange">ACTIVITY</span>
        </div>
        <div className="flex items-center gap-2.5 text-[#777777]">
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full border"
            style={{ borderColor: 'var(--border)' }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#333]" />
          </span>
          <span className="text-[13px]">No workers out right now.</span>
        </div>
      </section>

      {/* GOALS */}
      <section className="px-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target size={11} className="text-orange" />
            <span className="label-tech text-orange">GOALS</span>
          </div>
          <button
            onClick={onAjouterBut}
            aria-label="Ajouter un objectif"
            className="flex h-5 w-5 items-center justify-center rounded-full bg-orange/15 text-orange transition hover:bg-orange/30"
            style={{ boxShadow: '0 0 10px rgba(255,106,0,0.25)' }}
          >
            <Plus size={11} />
          </button>
        </div>

        <div className="flex flex-col gap-3">
          {buts.map((but) => (
            <div
              key={but.id}
              className="rounded-lg border p-3"
              style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <span className="text-[13px] leading-snug text-[#f5f5f5]">
                  {but.titre}
                </span>
                <span className="label-tech shrink-0 text-[9px] text-[#777777]">
                  {but.statut}
                </span>
              </div>
              <p className="mb-2 text-[11px] text-[#777777]">What this goal needs</p>
              <div className="flex flex-col gap-1.5">
                {but.requis.map((req) => {
                  const integ = INTEGRATIONS[req.id]
                  const Ic = integ.icone
                  const deja = connectes.has(req.id)
                  return (
                    <div key={req.id} className="flex items-center gap-2">
                      <Ic size={13} className="shrink-0 text-[#777777]" />
                      <span className="flex-1 truncate text-[12px] text-[#c7c7c7]">
                        {req.texte}
                      </span>
                      <button
                        onClick={() => !deja && onConnecter(req.id)}
                        disabled={deja}
                        className="label-tech shrink-0 rounded border px-2 py-0.5 text-[9px] transition"
                        style={{
                          borderColor: deja
                            ? 'rgba(32,232,120,0.35)'
                            : 'var(--border-orange)',
                          color: deja ? '#20E878' : '#FF8500',
                          background: deja ? 'rgba(32,232,120,0.06)' : 'transparent',
                        }}
                      >
                        {deja ? '✓' : 'CONNECT'}
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* GETTING STARTED : carte flottante */}
      <div className="mt-auto p-4">
        {!repliee && (
          <GettingStarted
            etapesFaites={etapesFaites}
            onOuvrirEtape={onOuvrirEtape}
            onReplier={() => setRepliee(true)}
          />
        )}
        {repliee && (
          <button
            onClick={() => setRepliee(false)}
            className="label-tech flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-[10px] transition hover:border-orange/40"
            style={{
              background: 'rgba(255,106,0,0.04)',
              borderColor: 'var(--border-orange)',
              boxShadow: '0 0 22px rgba(255,106,0,0.10)',
            }}
          >
            <span className="text-orange">GETTING STARTED</span>
            <span className="flex items-center gap-1.5 text-[#777777]">
              {etapesFaites.size}/4 <ChevronRight size={11} />
            </span>
          </button>
        )}
      </div>
      <span className="hidden"><Minus size={0} /></span>
    </aside>
  )
}

export { ETAPES_DEMARRAGE }
