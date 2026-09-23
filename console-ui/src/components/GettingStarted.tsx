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
        background: 'rgba(13,13,13,0.85)',
        borderColor: 'var(--border-orange)',
        boxShadow: '0 0 34px rgba(255,106,0,0.13), 0 8px 30px rgba(0,0,0,0.5)',
      }}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={12} className="text-orange" />
          <span className="label-tech text-[#c7c7c7]">GETTING STARTED</span>
        </div>
        <button
          onClick={onReplier}
          aria-label="Replier"
          className="rounded p-1 text-[#777777] transition hover:text-[#f5f5f5]"
        >
          <Minus size={13} />
        </button>
      </div>
      <div className="mb-1 flex items-baseline gap-2">
        <span className="text-[15px] font-semibold text-[#f5f5f5]">
          {etapesFaites.size}/4
        </span>
        <span className="text-[12px] text-[#777777]">
          {restantes === 1 ? 'One left' : `${restantes} left`}
        </span>
      </div>
      <p className="label-tech mb-2 text-[9px] text-[#777777]">
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
                className="text-[#777777] transition group-hover:translate-x-0.5 group-hover:text-orange"
              />
            </button>
          )
        })}
      </div>
    </div>
  )
}
