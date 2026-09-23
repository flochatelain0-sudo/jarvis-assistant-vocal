import { Search, Bell, Globe } from 'lucide-react'

interface Props {
  onOuvrirRecherche: () => void
}

export default function TopBar({ onOuvrirRecherche }: Props) {
  return (
    <header
      className="fixed inset-x-0 top-0 z-40 flex h-[60px] items-center justify-between border-b px-5"
      style={{ background: 'rgba(5,5,5,0.92)', borderColor: 'var(--border)' }}
    >
      <div className="label-tech text-orange" style={{ fontSize: 12, letterSpacing: '0.28em' }}>
        ZOEY_OS<span className="align-super text-[8px]">™</span>
      </div>
      <div className="flex items-center gap-4 text-[#777777]">
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
