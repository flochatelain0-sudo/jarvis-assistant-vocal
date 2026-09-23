import { X } from 'lucide-react'

interface Props {
  onFermer: () => void
  journal: { ts: number; categorie: string; titre: string }[]
  actions24h: number
  enAttente: number
  vie: { etat: string; modele: string; routage: string }
}

export default function ConsolePanel({ onFermer, journal, actions24h, enAttente, vie }: Props) {
  return (
    <div
      className="absolute inset-x-0 bottom-0 top-[100px] z-20 overflow-y-auto px-6 py-6"
      style={{
        background: 'rgba(5,5,5,0.86)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="mx-auto max-w-lg">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="label-tech text-orange" style={{ fontSize: 11 }}>CONSOLE</h2>
          <button onClick={onFermer} aria-label="Fermer" className="text-[#777777] transition hover:text-[#f5f5f5]">
            <X size={15} />
          </button>
        </div>

        <div className="mb-6 grid grid-cols-3 gap-2">
          <div className="rounded-lg border px-3 py-2.5" style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}>
            <div className="text-[19px] font-semibold text-[#f5f5f5]">{actions24h}</div>
            <div className="label-tech text-[8px] text-[#777777]">ACTIONS · 24H</div>
          </div>
          <div className="rounded-lg border px-3 py-2.5" style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}>
            <div className="text-[19px] font-semibold text-[#FF8500]">{enAttente}</div>
            <div className="label-tech text-[8px] text-[#777777]">TO CONFIRM</div>
          </div>
          <div className="rounded-lg border px-3 py-2.5" style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}>
            <div className="label-tech text-[11px] text-green" style={{ paddingTop: 4 }}>{vie.etat || 'veille'}</div>
            <div className="label-tech text-[8px] text-[#777777]">LIVE STATE</div>
          </div>
        </div>

        <h3 className="label-tech mb-3 text-[10px] text-[#777777]">WORKERS / ACTIVITY</h3>
        <div className="mb-6 rounded-lg border p-4" style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}>
          <span className="text-[13px] text-[#777777]">No workers out right now.</span>
        </div>

        <h3 className="label-tech mb-3 text-[10px] text-[#777777]">JOURNAL</h3>
        <div className="flex flex-col gap-1.5">
          {journal.length === 0 && (
            <div className="text-[12.5px] text-[#777777]">Rien pour l'instant.</div>
          )}
          {journal.slice(0, 12).map((j, i) => (
            <div
              key={i}
              className="flex items-baseline gap-2.5 rounded-lg border px-3.5 py-2.5"
              style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
            >
              <span className="label-tech shrink-0 text-[8.5px] text-orange/80">{j.categorie}</span>
              <span className="flex-1 truncate text-[12.5px] text-[#c7c7c7]">{j.titre}</span>
              <span className="label-tech shrink-0 text-[8.5px] text-[#555]">
                {new Date(j.ts * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          ))}
        </div>
        {(vie.modele || vie.routage) && (
          <p className="label-tech mt-5 text-[8.5px] text-[#555]">
            {vie.modele} {vie.routage ? `· MODE ${vie.routage}` : ''}
          </p>
        )}
      </div>
    </div>
  )
}
