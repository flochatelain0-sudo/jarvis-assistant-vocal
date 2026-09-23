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
      className="label-tech flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] transition"
      style={{
        color: mode === id ? '#FF8500' : '#c7c7c7',
        background: mode === id ? 'rgba(255,106,0,0.10)' : 'transparent',
        boxShadow: mode === id ? 'inset 0 0 0 1px var(--accent-ring)' : 'none',
      }}
    >
      <Ic size={11} />
      {label}
    </button>
  )

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="flex items-center gap-1 rounded-lg border px-2.5 py-1.5"
        style={{
          background: 'var(--panel-glass)',
          borderColor: 'var(--border-orange)',
          boxShadow: '0 0 26px rgba(255,106,0,0.14)',
        }}
      >
        {onglet('chat', MessageSquare, 'Chat')}
        {onglet('console', Terminal, 'Console')}
        {onglet('brain', Brain, 'Brain')}
        {onglet('integrations', Unplug, 'Integrations')}
        {onglet('configurer', Settings, 'Configure')}
      </div>
      <p className="label-tech text-[8.5px] text-[var(--placeholder)]">
        Chat · Console · Brain · Integrations · Configure · tap an item to open or close it
      </p>
    </div>
  )
}
