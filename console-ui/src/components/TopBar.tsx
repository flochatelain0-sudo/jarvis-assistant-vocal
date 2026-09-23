import { Search, Bell, Globe, Sun, Moon } from 'lucide-react'
import type { ModeGlobal } from '../lib/api'
import type { Theme } from '../lib/theme'

interface Props {
  onOuvrirRecherche: () => void
  mode: ModeGlobal
  onMode: (m: ModeGlobal) => void
  theme: Theme
  onTheme: () => void
}

const MANUEL_DESC = 'MANUAL — companions ask before acting.'
const AUTO_DESC = 'AUTO — companions act on their own. Deletes, sends and anything involving money always ask.'

export default function TopBar({ onOuvrirRecherche, mode, onMode, theme, onTheme }: Props) {
  const bouton = (v: ModeGlobal, label: string) => (
    <button
      onClick={() => onMode(v)}
      title={v === 'auto' ? AUTO_DESC : MANUEL_DESC}
      className="label-tech rounded-md px-2.5 py-1 text-[9.5px] transition"
      style={{
        color: mode === v ? 'var(--accent-bright)' : 'var(--muted)',
        background: mode === v ? 'var(--accent-soft)' : 'transparent',
        boxShadow: mode === v ? 'inset 0 0 0 1px var(--accent-ring)' : 'none',
      }}
    >
      {label}
    </button>
  )

  return (
    <header
      className="fixed inset-x-0 top-0 z-40 flex h-[60px] items-center justify-between border-b px-5"
      style={{ background: 'var(--panel-glass-strong)', borderColor: 'var(--border)' }}
    >
      <div className="label-tech text-orange" style={{ fontSize: 12, letterSpacing: '0.28em' }}>
        JARVIS_OS<span className="align-super text-[8px]">™</span>
      </div>
      <div className="flex items-center gap-4" style={{ color: 'var(--muted)' }}>
        <div
          className="flex items-center gap-1 rounded-lg border px-2 py-1"
          title="MANUAL — companions ask before acting.&#10;AUTO — companions act on their own.&#10;Deletes, sends and anything involving money always ask."
          style={{
            background: 'var(--panel-glass)',
            borderColor: mode === 'auto' ? 'rgba(32,232,120,0.45)' : 'var(--border-orange)',
            boxShadow: mode === 'auto' ? '0 0 20px rgba(32,232,120,0.16)' : 'none',
          }}
        >
          {bouton('manual', 'MANUAL')}
          {bouton('auto', 'AUTO')}
        </div>
        <button
          aria-label={theme === 'sombre' ? 'Thème clair' : 'Thème sombre'}
          title={theme === 'sombre' ? 'Passer en thème clair' : 'Passer en thème sombre'}
          onClick={onTheme}
          className="rounded-md p-1.5 transition hover:text-[var(--text)] hover:bg-white/5"
        >
          {theme === 'sombre' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button
          aria-label="Rechercher"
          onClick={onOuvrirRecherche}
          className="rounded-md p-1.5 transition hover:text-[var(--text)] hover:bg-white/5"
        >
          <Search size={16} />
        </button>
        <button
          aria-label="Notifications"
          className="relative rounded-md p-1.5 transition hover:text-[var(--text)] hover:bg-white/5"
        >
          <Bell size={16} />
          <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-orange" />
        </button>
        <button
          aria-label="Langue"
          className="rounded-md p-1.5 transition hover:text-[var(--text)] hover:bg-white/5"
        >
          <Globe size={16} />
        </button>
        <button
          aria-label="Profil"
          className="flex h-8 w-8 items-center justify-center rounded-full border text-orange transition hover:border-orange/60"
          style={{ background: 'var(--panel-up)', borderColor: 'var(--border)' }}
        >
          <span className="label-tech" style={{ letterSpacing: 0 }}>F</span>
        </button>
      </div>
    </header>
  )
}
