import { MessageSquare, Terminal, Settings, Brain, Unplug, type LucideIcon } from 'lucide-react'

export type ModeCentre = 'chat' | 'console' | 'configurer' | 'brain' | 'integrations' | null

interface Props {
  mode: ModeCentre
  onChoisir: (mode: Exclude<ModeCentre, null>) => void
}

export default function WorkspaceControls({ mode, onChoisir }: Props) {
  const onglet = (id: Exclude<ModeCentre, null>, Ic: LucideIcon, label: string) => (
    <button
      onClick={() => onChoisir(id)}
      title={label}
      aria-label={label}
      className="flex h-8 w-8 items-center justify-center rounded-md transition"
      style={{
        color: mode === id ? 'var(--accent-bright)' : 'var(--muted)',
        background: mode === id ? 'var(--accent-soft)' : 'transparent',
        boxShadow: mode === id ? 'inset 0 0 0 1px var(--accent-ring)' : 'none',
      }}
    >
      <Ic size={14} />
    </button>
  )

  return (
    <div
      className="flex items-center gap-1 rounded-full border px-2 py-1"
      style={{
        background: 'var(--panel-glass)',
        borderColor: 'var(--border)',
      }}
    >
      {onglet('chat', MessageSquare, 'Chat')}
      {onglet('console', Terminal, 'Console')}
      {onglet('brain', Brain, 'Brain')}
      {onglet('integrations', Unplug, 'Integrations')}
      {onglet('configurer', Settings, 'Configure')}
    </div>
  )
}
