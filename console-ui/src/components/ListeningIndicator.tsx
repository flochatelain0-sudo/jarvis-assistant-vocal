import { Mic, MicOff } from 'lucide-react'

interface Props {
  actif: boolean
  onBasculer: () => void
  reco: {
    actif: boolean
    partiel: string
    erreur: string | null
    disponible: boolean
  }
  transcription?: string
}

export default function ListeningIndicator({ actif, onBasculer, reco, transcription }: Props) {
  const ecouteEnCours = reco.actif
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={onBasculer}
        aria-label={ecouteEnCours ? 'Écoute en cours' : actif ? "Réactiver l'écoute" : "Couper l'écoute"}
        title={ecouteEnCours ? 'Reconnaissance vocale active' : actif ? 'Micro actif' : 'Micro en pause'}
        className="flex items-center gap-2.5 rounded-full border px-5 py-1.5 transition-all"
        style={{
          borderColor: ecouteEnCours
            ? 'rgba(32,232,120,0.45)'
            : actif
              ? 'rgba(255,110,0,0.25)'
              : 'var(--border)',
          background: 'var(--panel-glass)',
          boxShadow: ecouteEnCours
            ? '0 0 24px rgba(32,232,120,0.18)'
            : actif
              ? '0 0 24px rgba(255,106,0,0.14)'
              : 'none',
        }}
      >
        {ecouteEnCours ? (
          <span className="point-vert h-2 w-2 rounded-full bg-green" />
        ) : actif ? (
          <Mic size={10} className="text-orange" />
        ) : (
          <MicOff size={10} className="text-[#777777]" />
        )}
        <span
          className="label-tech"
          style={{ color: ecouteEnCours ? '#20E878' : actif ? '#FF8500' : '#777777' }}
        >
          {ecouteEnCours ? 'LISTENING' : actif ? 'READY' : 'PAUSED'}
        </span>
        <span className="label-tech text-[#777777]/60">
          {'·'.repeat(ecouteEnCours ? 9 : 5)}
        </span>
        <Mic size={11} className={ecouteEnCours ? 'text-green' : actif ? 'text-orange' : 'text-[#777777]'} />
      </button>
      {!reco.disponible && (
        <span className="label-tech text-[9px] text-[#555]">
          reconnaissance vocale indisponible sur ce navigateur
        </span>
      )}
      {reco.erreur && (
        <span className="label-tech text-[9px] text-[#777777]">{reco.erreur}</span>
      )}
      {reco.partiel && (
        <span className="label-tech max-w-[420px] truncate text-[10px] text-green/80">
          {reco.partiel}
        </span>
      )}
      {transcription && !reco.partiel && (
        <span className="label-tech max-w-[420px] truncate text-[10px] text-orange/80">
          « {transcription} » envoyé à Jarvis
        </span>
      )}
    </div>
  )
}
