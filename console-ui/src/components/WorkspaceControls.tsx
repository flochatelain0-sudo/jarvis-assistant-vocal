import { MessageSquare, Terminal, Settings, Sparkle, type LucideIcon } from 'lucide-react'

export type ModeCentre = 'chat' | 'console' | 'configurer' | null

interface Props {
  mode: ModeCentre
  onChoisir: (mode: Exclude<ModeCentre, null>) => void
  credits: number
}

export default function WorkspaceControls({ mode, onChoisir, credits }: Props) {
  const onglet = (id: Exclude<ModeCentre, null>, Ic: LucideIcon, label: string) => (
    <button
      onClick={() => onChoisir(id)}
      className="label-tech flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] transition"
      style={{
        color: mode === id ? '#FF8500' : '#c7c7c7',
        background: mode === id ? 'rgba(255,106,0,0.10)' : 'transparent',
        boxShadow: mode === id ? 'inset 0 0 0 1px rgba(255,110,0,0.35)' : 'none',
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
          background: 'rgba(8,8,8,0.8)',
          borderColor: 'var(--border-orange)',
          boxShadow: '0 0 26px rgba(255,106,0,0.14)',
        }}
      >
        {onglet('chat', MessageSquare, 'Chat')}
        {onglet('console', Terminal, 'Console')}
        {onglet('configurer', Settings, 'Configure')}
        <span className="mx-1.5 h-4 w-px" style={{ background: 'var(--border)' }} />
        <div className="label-tech flex items-center gap-1.5 px-2 text-[10px] text-[#c7c7c7]">
          <Sparkle size={11} className="text-orange" />
          Credits
        </div>
        <span
          className="label-tech rounded-full border px-2.5 py-0.5 text-[10px] text-[#f5f5f5]"
          style={{ borderColor: 'var(--border-orange)', background: 'rgba(255,106,0,0.07)' }}
        >
          {credits}
        </span>
      </div>
      <p className="label-tech text-[8.5px] text-[#555]">
        Chat · Console · Configure · tap an item to open or close it · your credits on the right
      </p>
    </div>
  )
}
