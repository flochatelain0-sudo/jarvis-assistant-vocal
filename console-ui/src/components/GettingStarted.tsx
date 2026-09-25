import { ChevronRight, Minus, Sparkles } from 'lucide-react'

interface Props {
  etapesFaites: Set<number>
  onOuvrirEtape: (i: number) => void
  onReplier: () => void
}

const ETAPES = [
  'Take the tour',
  'Connect your platforms and tools',
  'Put something on autopilot',
  'Watch Jarvis work',
]

export default function GettingStarted({ etapesFaites, onOuvrirEtape, onReplier }: Props) {
  const restantes = 4 - etapesFaites.size
  return (
    <div
      className="rounded-xl border p-3.5"
      style={{
        background: 'var(--panel-glass-strong)',
        borderColor: 'var(--border-orange)',
        boxShadow: '0 0 34px rgba(255,106,0,0.13), 0 8px 30px rgba(0,0,0,0.5)',
      }}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={12} className="text-orange" />
          <span className="label-tech text-[var(--dim)]">GETTING STARTED</span>
        </div>
        <button
          onClick={onReplier}
          aria-label="Replier"
          className="rounded p-1 text-[var(--muted)] transition hover:text-[var(--text)]"
        >
          <Minus size={13} />
        </button>
      </div>
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-[15px] font-semibold text-[var(--text)]">
          {etapesFaites.size}/4
        </span>
        <span className="text-[12px] text-[var(--muted)]">
          {restantes === 1 ? 'One left' : `${restantes} left`}
        </span>
      </div>
      <p className="label-tech mb-2 text-[9px] text-[var(--muted)]">
        TAP A STEP TO OPEN IT
      </p>
      <div className="flex flex-col">
        {ETAPES.map((etape, i) => {
          const fait = etapesFaites.has(i)
          return (
            <button
              key={etape}
              onClick={() => onOuvrirEtape(i)}
              className="group flex items-center justify-between border-t py-2 text-left transition"
              style={{ borderColor: 'var(--border)' }}
            >
              <span
                className="text-[12.5px] transition"
                style={{
                  color: fait ? '#777777' : '#c7c7c7',
                  textDecoration: fait ? 'line-through' : 'none',
                }}
              >
                {etape}
              </span>
              <ChevronRight
                size={12}
                className="text-[var(--muted)] transition group-hover:translate-x-0.5 group-hover:text-orange"
              />
            </button>
          )
        })}
      </div>
    </div>
  )
}
