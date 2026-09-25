import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { INTEGRATIONS, type IntegrationId } from '../lib/integrations'

interface Props {
  onFermer: () => void
  connectes: Set<IntegrationId>
  onConnecter: (id: IntegrationId) => void
}

interface Reglage {
  cle: string
  label: string
  description: string
}

const REGLAGES: Reglage[] = [
  { cle: 'voix', label: 'Voice', description: 'Jarvis répond à voix haute via le moteur TTS de Jarvis.' },
  { cle: 'notifications', label: 'Notifications', description: 'Préviens-moi quand une action me concerne.' },
  { cle: 'autopilote', label: 'Autopilot', description: 'Exécute les actions sans risque (95/5 : lectures N1) sans confirmer.' },
  { cle: 'style', label: 'Response style', description: 'Concis par défaut, développé si tu préfères.' },
]

export default function ConfigurationPanel({ onFermer, connectes, onConnecter }: Props) {
  const [reglages, setReglages] = useState<Record<string, boolean>>({
    voix: true,
    notifications: true,
    autopilote: false,
    style: false,
  })

  return (
    <div
      className="absolute inset-x-0 bottom-0 top-[100px] z-20 overflow-y-auto border-t px-6 py-6"
      style={{
        background: 'var(--panel-glass-strong)',
        borderColor: 'var(--border-orange)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="mx-auto max-w-lg">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="label-tech text-orange" style={{ fontSize: 11 }}>CONFIGURE</h2>
          <button onClick={onFermer} aria-label="Fermer" className="text-[var(--muted)] transition hover:text-[var(--text)]">
            <X size={15} />
          </button>
        </div>

        <div className="mb-7 flex flex-col gap-3">
          {REGLAGES.map((r) => (
            <div
              key={r.cle}
              className="flex items-center justify-between rounded-lg border px-4 py-3"
              style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
            >
              <div className="pr-3">
                <div className="text-[13.5px] text-[var(--text)]">{r.label}</div>
                <div className="text-[11.5px] text-[var(--muted)]">{r.description}</div>
              </div>
              <button
                role="switch"
                aria-checked={reglages[r.cle]}
                onClick={() => setReglages((p) => ({ ...p, [r.cle]: !p[r.cle] }))}
                className="relative h-5 w-9 shrink-0 rounded-full border transition-colors"
                style={{
                  borderColor: reglages[r.cle] ? 'rgba(255,106,0,0.5)' : 'var(--border)',
                  background: reglages[r.cle] ? 'rgba(255,106,0,0.25)' : '#151515',
                }}
              >
                <span
                  className="absolute top-[2px] h-3.5 w-3.5 rounded-full transition-all"
                  style={{
                    left: reglages[r.cle] ? 18 : 3,
                    background: reglages[r.cle] ? '#FF8500' : '#555',
                  }}
                />
              </button>
            </div>
          ))}
        </div>

        <h3 className="label-tech mb-3 text-[10px] text-[var(--muted)]">CONNECTED PLATFORMS</h3>
        <div className="flex flex-col gap-2">
          {(Object.keys(INTEGRATIONS) as IntegrationId[]).map((id) => {
            const integ = INTEGRATIONS[id]
            const Ic = integ.icone
            const deja = connectes.has(id)
            return (
              <div
                key={id}
                className="flex items-center gap-3 rounded-lg border px-4 py-3"
                style={{
                  background: 'var(--panel)',
                  borderColor: deja ? 'rgba(32,232,120,0.3)' : 'var(--border)',
                }}
              >
                <Ic size={15} className={deja ? 'text-green' : 'text-[var(--muted)]'} />
                <div className="flex-1">
                  <div className="label-tech text-[10px] text-[var(--dim)]">{integ.nom}</div>
                </div>
                {deja ? (
                  <span className="label-tech flex items-center gap-1 text-[9px] text-green">
                    <Check size={11} /> CONNECTED
                  </span>
                ) : (
                  <button
                    onClick={() => onConnecter(id)}
                    className="label-tech rounded border px-2.5 py-1 text-[9px] text-[var(--accent-bright)] transition hover:bg-orange/10"
                    style={{ borderColor: 'var(--border-orange)' }}
                  >
                    CONNECT
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
