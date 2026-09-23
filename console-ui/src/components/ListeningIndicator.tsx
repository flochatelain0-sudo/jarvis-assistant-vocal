interface Props {
  actif: boolean
  onBasculer: () => void
}

export default function ListeningIndicator({ actif, onBasculer }: Props) {
  return (
    <button
      onClick={onBasculer}
      aria-label={actif ? "Couper l'écoute" : 'Réactiver l’écoute'}
      title={actif ? 'Micro actif' : 'Micro en pause'}
      className="flex h-9 w-9 items-center justify-center rounded-full border transition-all"
      style={{
        borderColor: actif ? 'rgba(32,232,120,0.45)' : 'var(--border)',
        background: 'var(--panel-glass)',
        boxShadow: actif ? '0 0 18px rgba(32,232,120,0.18)' : 'none',
      }}
    >
      {actif ? (
        <span className="point-vert block h-2 w-2 rounded-full bg-green" />
      ) : (
        <span className="block h-2 w-2 rounded-full" style={{ background: 'var(--muted)' }} />
      )}
    </button>
  )
}
