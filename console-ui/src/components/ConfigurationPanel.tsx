import { useEffect, useState } from 'react'
import { X, Check } from 'lucide-react'
import { INTEGRATIONS, type IntegrationId } from '../lib/integrations'
import { api } from '../lib/api'

interface Props {
  onFermer: () => void
  connectes: Set<IntegrationId>
  onConnecter: (id: IntegrationId) => void
}

type Mode = 'manual' | 'auto'

function ChoixMode({ mode, onChoisir }: { mode: Mode; onChoisir: (m: Mode) => void }) {
  const options: { id: Mode; titre: string; texte: string }[] = [
    { id: 'manual', titre: 'MANUAL', texte: "Companions ask before acting." },
    { id: 'auto', titre: 'AUTO', texte: "Companions act on their own." },
  ]
  return (
    <div className="mb-7">
      <h3 className="label-tech mb-3 text-[10px] text-[#777777]">MODE</h3>
      <div className="grid grid-cols-2 gap-2">
        {options.map((o) => {
          const actif = mode === o.id
          return (
            <button
              key={o.id}
              onClick={() => onChoisir(o.id)}
              className="rounded-lg border px-4 py-3 text-left transition"
              style={{
                background: actif ? 'rgba(255,106,0,0.10)' : 'var(--panel)',
                borderColor: actif ? 'rgba(255,110,0,0.45)' : 'var(--border)',
                boxShadow: actif ? '0 0 18px rgba(255,106,0,0.12)' : 'none',
              }}
            >
              <div className="label-tech text-[11px]" style={{ color: actif ? '#FF8500' : '#c7c7c7' }}>
                {o.titre}
              </div>
              <div className="mt-1 text-[11.5px] leading-snug text-[#777777]">{o.texte}</div>
            </button>
          )
        })}
      </div>
      <p className="mt-2.5 text-[11px] leading-snug text-[#777777]">
        Deletes, sends and anything involving money always ask.
      </p>
    </div>
  )
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
  const [mode, setMode] = useState<Mode>('manual')

  // mode reel depuis config.yaml (securite.autopilote) ; sauvegarde au choix
  useEffect(() => {
    api.mode().then((m) => {
      if (m && m.mode) setMode(m.mode)
    })
  }, [])

  const choisirMode = (m: Mode) => {
    setMode(m)
    api.definirMode(m)
  }

  return (
    <div
      className="absolute inset-x-0 bottom-0 top-[100px] z-20 overflow-y-auto border-t px-6 py-6"
      style={{
        background: 'rgba(5,5,5,0.86)',
        borderColor: 'var(--border-orange)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="mx-auto max-w-lg">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="label-tech text-orange" style={{ fontSize: 11 }}>CONFIGURE</h2>
          <button onClick={onFermer} aria-label="Fermer" className="text-[#777777] transition hover:text-[#f5f5f5]">
            <X size={15} />
          </button>
        </div>

        <ChoixMode mode={mode} onChoisir={choisirMode} />

        <div className="mb-7 flex flex-col gap-3">
          {REGLAGES.map((r) => (
            <div
              key={r.cle}
              className="flex items-center justify-between rounded-lg border px-4 py-3"
              style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
            >
              <div className="pr-3">
                <div className="text-[13.5px] text-[#f5f5f5]">{r.label}</div>
                <div className="text-[11.5px] text-[#777777]">{r.description}</div>
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

        <h3 className="label-tech mb-3 text-[10px] text-[#777777]">CONNECTED PLATFORMS</h3>
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
                <Ic size={15} className={deja ? 'text-green' : 'text-[#777777]'} />
                <div className="flex-1">
                  <div className="label-tech text-[10px] text-[#c7c7c7]">{integ.nom}</div>
                </div>
                {deja ? (
                  <span className="label-tech flex items-center gap-1 text-[9px] text-green">
                    <Check size={11} /> CONNECTED
                  </span>
                ) : (
                  <button
                    onClick={() => onConnecter(id)}
                    className="label-tech rounded border px-2.5 py-1 text-[9px] text-[#FF8500] transition hover:bg-orange/10"
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
