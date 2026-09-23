import { Activity, Target, Zap, Monitor, Plus, X } from 'lucide-react'
import type { But, Automation, IntegrationEtat } from '../lib/api'
import { INTEGRATIONS } from '../lib/integrations'
import GettingStarted from './GettingStarted'

interface Props {
  buts: But[]
  automations: Automation[]
  integrations: Record<string, IntegrationEtat>
  connectes: Set<string>
  onConnecter: (id: string) => void
  onAjouterBut: () => void
  onSupprimerBut: (id: string) => void
  onOuvrirEtape: (i: number) => void
  etapesFaites: Set<number>
  ouverte: boolean
  onFermer: () => void
}

export default function ConsoleSidebar({
  buts,
  automations,
  integrations,
  connectes,
  onConnecter,
  onAjouterBut,
  onSupprimerBut,
  onOuvrirEtape,
  etapesFaites,
  ouverte,
  onFermer,
}: Props) {
  if (!ouverte) return null

  const actives = automations.filter((a) => a.active).length

  return (
    <aside
      className="flex flex-col overflow-y-auto border-r"
      style={{ background: 'var(--panel-glass)', borderColor: 'var(--border)' }}
    >
      {/* entete CONSOLE */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full bg-orange"
            style={{ boxShadow: '0 0 10px rgba(255,106,0,0.7)' }}
          />
          <span className="label-tech text-[var(--dim)]">CONSOLE</span>
        </div>
        <button
          onClick={onFermer}
          aria-label="Fermer la console"
          className="rounded p-1 text-[var(--muted)] transition hover:text-[var(--text)]"
        >
          <X size={13} />
        </button>
      </div>

      {/* ACTIVITY : journal reel */}
      <section className="px-4 pb-4">
        <div className="mb-3 flex items-center gap-2">
          <Activity size={11} className="text-orange" />
          <span className="label-tech text-orange">ACTIVITY</span>
        </div>
        <div className="flex items-center gap-2.5 text-[var(--muted)]">
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full border"
            style={{ borderColor: 'var(--border)' }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--panel-up)]" />
          </span>
          <span className="text-[13px]">No workers out right now.</span>
        </div>
      </section>

      {/* AUTOMATIONS : le vrai planificateur */}
      <section className="px-4 pb-4">
        <div className="mb-3 flex items-center gap-2">
          <Zap size={11} className="text-orange" />
          <span className="label-tech text-orange">AUTOMATIONS</span>
        </div>
        {actives === 0 ? (
          <div className="text-[12px] text-[var(--muted)]">
            Nothing runs on its own yet.
          </div>
        ) : (
          automations.filter((a) => a.active).map((a) => (
            <div key={a.id} className="mb-1.5 flex items-center gap-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-green" />
              <span className="flex-1 truncate text-[12.5px] text-[var(--dim)]">{a.nom}</span>
              <span className="label-tech text-[8.5px] text-[var(--placeholder)]">{a.moment}</span>
            </div>
          ))
        )}
      </section>

      {/* LOCAL MACHINE : acces reel */}
      <section className="px-4 pb-4">
        <div className="mb-3 flex items-center gap-2">
          <Monitor size={11} className="text-orange" />
          <span className="label-tech text-orange">LOCAL MACHINE</span>
        </div>
        {connectes.has('pc') ? (
          <div className="text-[12px] text-[var(--dim)]">
            Astra PC control approved.
          </div>
        ) : (
          <div className="text-[12px] text-[var(--muted)]">
            No apps approved yet — the first request arrives in chat.
          </div>
        )}
      </section>

      {/* GOALS : buts persistes */}
      <section className="px-4 pb-4">
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
                <span className="text-[13px] leading-snug text-[var(--text)]">
                  {but.titre}
                </span>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="label-tech text-[9px] text-[var(--muted)]">
                    {but.statut}
                  </span>
                  <button
                    onClick={() => onSupprimerBut(but.id)}
                    aria-label="Supprimer l'objectif"
                    className="text-[var(--placeholder)] transition hover:text-[var(--text)]"
                  >
                    <X size={11} />
                  </button>
                </div>
              </div>
              <p className="mb-2 text-[11px] text-[var(--muted)]">What this goal needs</p>
              <div className="flex flex-col gap-1.5">
                {but.requis.map((req) => {
                  const integ = INTEGRATIONS[req.id as keyof typeof INTEGRATIONS]
                  const etatInteg = integrations[req.id]
                  const deja = req.connecte || (etatInteg && etatInteg.connecte)
                  const Ic = integ ? integ.icone : undefined
                  return (
                    <div key={req.id} className="flex items-center gap-2">
                      {Ic ? (
                        <Ic size={13} className="shrink-0 text-[var(--muted)]" />
                      ) : (
                        <span className="h-3.5 w-3.5 shrink-0 rounded-full border" style={{ borderColor: 'var(--border)' }} />
                      )}
                      <span className="flex-1 truncate text-[12px] text-[var(--dim)]">
                        {etatInteg
                          ? `${deja ? 'Connected — ' : ''}${etatInteg.nom}`
                          : req.id}
                      </span>
                      <button
                        onClick={() => !deja && onConnecter(req.id)}
                        disabled={Boolean(deja)}
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
        <GettingStarted
          etapesFaites={etapesFaites}
          onOuvrirEtape={onOuvrirEtape}
          onReplier={() => {}}
        />
      </div>
    </aside>
  )
}
