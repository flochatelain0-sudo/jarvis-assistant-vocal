import { useState } from 'react'
import { Mic, MicOff } from 'lucide-react'

interface Props {
  actif: boolean
  onBasculer: () => void
}

export default function ListeningIndicator({ actif, onBasculer }: Props) {
  const [erreur, setErreur] = useState(false)

  const basculer = () => {
    onBasculer()
    setErreur(false)
    if (actif && 'webkitSpeechRecognition' in window) {
      // coupure propre si une reconnaissance etait ouverte
      try {
        const w = window as unknown as { zoeyReco?: { stop: () => void } }
        w.zoeyReco?.stop()
      } catch {
        setErreur(true)
      }
    }
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={basculer}
        className="flex items-center gap-2.5 rounded-full border px-5 py-1.5 transition-all"
        style={{
          borderColor: actif ? 'rgba(32,232,120,0.45)' : 'var(--border)',
          background: 'rgba(5,5,5,0.55)',
          boxShadow: actif ? '0 0 24px rgba(32,232,120,0.18)' : 'none',
        }}
      >
        {actif ? (
          <span className="point-vert h-2 w-2 rounded-full bg-green" />
        ) : (
          <MicOff size={10} className="text-[#777777]" />
        )}
        <span className="label-tech" style={{ color: actif ? '#20E878' : '#777777' }}>
          {actif ? 'LISTENING' : 'PAUSED'}
        </span>
        <span className="label-tech text-[#777777]/60">
          {'·'.repeat(actif ? 9 : 5)}
        </span>
        <Mic size={11} className={actif ? 'text-green' : 'text-[#777777]'} />
      </button>
      {erreur && (
        <span className="label-tech text-[10px] text-[#777777]">
          micro indisponible — mode simulé
        </span>
      )}
    </div>
  )
}
