import { Check } from 'lucide-react'
import { INTEGRATIONS, type IntegrationId } from '../lib/integrations'

interface Props {
  id: IntegrationId | null
  connectes: Set<IntegrationId>
  onAnnuler: () => void
  onConnecter: (id: IntegrationId) => void
}

export default function ConnectionModal({ id, connectes, onAnnuler, onConnecter }: Props) {
  if (!id) return null
  const integ = INTEGRATIONS[id]
  const Ic = integ.icone
  const deja = connectes.has(id)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(6px)' }}
      onClick={onAnnuler}
    >
      <div
        className="w-[380px] rounded-xl border p-6"
        style={{
          background: '#0d0d0d',
          borderColor: 'var(--border-orange)',
          boxShadow: '0 0 44px rgba(255,106,0,0.16), 0 20px 60px rgba(0,0,0,0.6)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center gap-2.5">
          <Ic size={16} className="text-orange" />
          <h2 className="label-tech text-[11px] text-[#f5f5f5]">
            CONNECT {integ.nom}
          </h2>
        </div>
        <p className="mb-6 text-[13.5px] leading-relaxed text-[#c7c7c7]">
          {integ.description}
        </p>
        {deja ? (
          <div className="label-tech flex items-center justify-center gap-2 rounded-lg border py-3 text-[10px] text-green"
            style={{ borderColor: 'rgba(32,232,120,0.35)', background: 'rgba(32,232,120,0.06)' }}>
            <Check size={13} /> Connected ✓
          </div>
        ) : (
          <div className="flex justify-end gap-2">
            <button
              onClick={onAnnuler}
              className="label-tech rounded-lg border px-4 py-2 text-[10px] text-[#777777] transition hover:text-[#f5f5f5]"
              style={{ borderColor: 'var(--border)' }}
            >
              CANCEL
            </button>
            <button
              onClick={() => onConnecter(id)}
              className="label-tech rounded-lg px-4 py-2 text-[10px] text-black transition hover:brightness-110"
              style={{ background: '#FF6A00', boxShadow: '0 0 16px rgba(255,106,0,0.35)' }}
            >
              CONNECT
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
