import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  page: number
  nbPages: number
  onPage: (p: number) => void
}

export default function ZoeyBranding({ page, nbPages, onPage }: Props) {
  return (
    <div className="flex flex-col items-center gap-1">
      <h1
        className="label-tech text-orange"
        style={{ fontSize: 15, letterSpacing: '0.85em', textIndent: '0.85em' }}
      >
        JARVIS
      </h1>
      <p className="label-tech text-[8.5px] text-[#777777]">
        ORCHESTRATOR&nbsp;&nbsp;&nbsp;THE VOICE OF YOUR WORLD
      </p>
      <div className="mt-1.5 flex items-center gap-3">
        <button
          aria-label="Précédent"
          onClick={() => onPage((page - 1 + nbPages) % nbPages)}
          className="flex h-6 w-6 items-center justify-center rounded-full border text-[#777777] transition hover:border-orange/50 hover:text-orange"
          style={{ borderColor: 'var(--border)' }}
        >
          <ChevronLeft size={12} />
        </button>
        <div className="flex items-center gap-1.5">
          {Array.from({ length: nbPages }).map((_, i) => (
            <button
              key={i}
              aria-label={`Page ${i + 1}`}
              onClick={() => onPage(i)}
              className="h-1 rounded-full transition-all"
              style={{
                width: i === page ? 14 : 5,
                background: i === page ? '#FF6A00' : '#333',
                boxShadow: i === page ? '0 0 8px rgba(255,106,0,0.5)' : 'none',
              }}
            />
          ))}
        </div>
        <button
          aria-label="Suivant"
          onClick={() => onPage((page + 1) % nbPages)}
          className="flex h-6 w-6 items-center justify-center rounded-full border text-[#777777] transition hover:border-orange/50 hover:text-orange"
          style={{ borderColor: 'var(--border)' }}
        >
          <ChevronRight size={12} />
        </button>
      </div>
    </div>
  )
}
