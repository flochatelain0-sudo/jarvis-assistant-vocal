import { Search, Bell, Globe } from 'lucide-react'
import type { ModeGlobal } from '../lib/api'

interface Props {
  onOuvrirRecherche: () => void
  mode: ModeGlobal
  onMode: (m: ModeGlobal) => void
}

const MANUEL_DESC = 'MANUAL — companions ask before acting.'
const AUTO_DESC = 'AUTO — companions act on their own. Deletes, sends and anything involving money always ask.'

export default function TopBar({ onOuvrirRecherche, mode, onMode }: Props) {
  const bouton = (v: ModeGlobal, label: string) => (
    <button
      onClick={() => onMode(v)}
      title={v === 'auto' ? AUTO_DESC : MANUEL_DESC}
      className="label-tech rounded-md px-2.5 py-1 text-[9.5px] transition"
      style={{
        color: mode === v ? '#FF8500' : '#777777',
        background: mode === v ? 'rgba(255,106,0,0.10)' : 'transparent',
        boxShadow: mode === v ? 'inset 0 0 0 1px rgba(255,110,0,0.35)' : 'none',
      }}
    >
      {label}
    </button>
  )

  return (
    <header
      className="fixed inset-x-0 top-0 z-40 flex h-[60px] items-center justify-between border-b px-5"
      style={{ background: 'rgba(5,5,5,0.92)', borderColor: 'var(--border)' }}
    >
      <div className="label-tech text-orange" style={{ fontSize: 12, letterSpacing: '0.28em' }}>
        JARVIS_OS<span className="align-super text-[8px]">™</span>
      </div>
      <div className="flex items-center gap-4 text-[#777777]">
        <div
          className="flex items-center gap-1 rounded-lg border px-2 py-1"
          title="MANUAL — companions ask before acting.&#10;AUTO — companions act on their own.&#10;Deletes, sends and anything involving money always ask."
          style={{
            background: 'rgba(13,13,13,0.9)',
            borderColor: mode === 'auto' ? 'rgba(32,232,120,0.45)' : 'var(--border-orange)',
            boxShadow: mode === 'auto' ? '0 0 20px rgba(32,232,120,0.16)' : 'none',
          }}
        >
          {bouton('manual', 'MANUAL')}
          {bouton('auto', 'AUTO')}
        </div>
        <button
          aria-label="Rechercher"
          onClick={onOuvrirRecherche}
          className="rounded-md p-1.5 transition hover:text-[#f5f5f5] hover:bg-white/5"
        >
          <Search size={16} />
        </button>
        <button
          aria-label="Notifications"
          className="relative rounded-md p-1.5 transition hover:text-[#f5f5f5] hover:bg-white/5"
        >
          <Bell size={16} />
          <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-orange" />
        </button>
        <button
          aria-label="Langue"
          className="rounded-md p-1.5 transition hover:text-[#f5f5f5] hover:bg-white/5"
        >
          <Globe size={16} />
        </button>
        <button
          aria-label="Profil"
          className="flex h-8 w-8 items-center justify-center rounded-full border text-orange transition hover:border-orange/60"
          style={{ background: '#151515', borderColor: 'var(--border)' }}
        >
          <span className="label-tech" style={{ letterSpacing: 0 }}>F</span>
        </button>
      </div>
    </header>
  )
}
