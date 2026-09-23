import { useEffect, useRef, useState } from 'react'
import { Plus, X } from 'lucide-react'

interface Props {
  ouverte: boolean
  onFermer: () => void
  onCreer: (titre: string) => void
}

export default function ButModal({ ouverte, onFermer, onCreer }: Props) {
  const [titre, setTitre] = useState('')
  const champRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (ouverte) {
      setTitre('')
      setTimeout(() => champRef.current?.focus(), 30)
    }
  }, [ouverte])

  if (!ouverte) return null

  const valider = () => {
    const propre = titre.trim()
    if (!propre) return
    onCreer(propre)
    onFermer()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'var(--overlay)', backdropFilter: 'blur(6px)' }}
      onClick={onFermer}
    >
      <div
        className="w-[380px] rounded-xl border p-6"
        style={{
          background: 'var(--modal)',
          borderColor: 'var(--border-orange)',
          boxShadow: '0 0 44px rgba(255,106,0,0.16), 0 20px 60px rgba(0,0,0,0.6)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Plus size={15} className="text-orange" />
            <h2 className="label-tech text-[11px] text-[var(--text)]">NEW GOAL</h2>
          </div>
          <button
            aria-label="Fermer"
            onClick={onFermer}
            className="text-[var(--placeholder)] transition hover:text-[var(--text)]"
          >
            <X size={14} />
          </button>
        </div>
        <p className="mb-4 text-[12.5px] leading-relaxed text-[var(--muted)]">
          Decris ce que Jarvis doit garder sous controle pour toi.
        </p>
        <input
          ref={champRef}
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') valider()
            if (e.key === 'Escape') onFermer()
          }}
          placeholder="Ex. Garder ma boite mail a zero chaque soir…"
          className="mb-5 w-full rounded-lg border px-3 py-2.5 text-[13.5px] text-[var(--text)] outline-none placeholder:text-[var(--placeholder)]"
          style={{ background: 'rgba(5,5,5,0.8)', borderColor: 'var(--border)' }}
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onFermer}
            className="label-tech rounded-lg border px-4 py-2 text-[9.5px] text-[var(--muted)] transition hover:text-[var(--text)]"
            style={{ borderColor: 'var(--border)' }}
          >
            ANNULER
          </button>
          <button
            onClick={valider}
            disabled={!titre.trim()}
            className="label-tech rounded-lg bg-orange px-4 py-2 text-[9.5px] text-[var(--bg2)] transition enabled:hover:brightness-110 disabled:opacity-30"
          >
            CREER
          </button>
        </div>
      </div>
    </div>
  )
}
