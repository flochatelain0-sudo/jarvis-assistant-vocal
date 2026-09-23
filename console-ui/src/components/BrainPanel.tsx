import { useEffect, useState } from 'react'
import { Brain as BrainIcon, FileText, Upload, X } from 'lucide-react'
import { api, type Brain as BrainEtat, type DocumentConnaissance } from '../lib/api'

interface Props {
  onFermer: () => void
}

const ZONES: { cle: keyof BrainEtat; titre: string }[] = [
  { cle: 'preferences', titre: 'PREFERENCES' },
  { cle: 'people', titre: 'PEOPLE' },
  { cle: 'projects', titre: 'PROJECTS' },
  { cle: 'facts', titre: 'FACTS' },
]

export default function BrainPanel({ onFermer }: Props) {
  const [cerveau, setCerveau] = useState<BrainEtat | null>(null)
  const [documents, setDocuments] = useState<DocumentConnaissance[]>([])
  const [titre, setTitre] = useState('')
  const [contenu, setContenu] = useState('')
  const [envoi, setEnvoi] = useState(false)

  useEffect(() => {
    api.brain().then((b) => b && setCerveau(b))
    api.knowledge().then((k) => k && setDocuments(k.documents))
  }, [])

  const ajouter = async () => {
    if (!contenu.trim() || envoi) return
    setEnvoi(true)
    const ok = await api.knowledgeAjouter(titre.trim(), contenu.trim())
    setEnvoi(false)
    if (ok) {
      setTitre('')
      setContenu('')
      const k = await api.knowledge()
      if (k) setDocuments(k.documents)
    }
  }

  return (
    <div
      className="absolute inset-x-0 bottom-0 top-[100px] z-20 overflow-y-auto border-t px-6 py-6"
      style={{
        background: 'rgba(5,5,5,0.86)',
        borderColor: 'var(--border-orange)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div className="mx-auto max-w-2xl">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BrainIcon size={14} className="text-orange" />
            <h2 className="label-tech text-orange" style={{ fontSize: 11 }}>BRAIN</h2>
            <span className="text-[11.5px] text-[#777777]">
              Documents, memories and previous conversations — everything you and Jarvis work on together.
            </span>
          </div>
          <button onClick={onFermer} aria-label="Fermer" className="text-[#777777] transition hover:text-[#f5f5f5]">
            <X size={15} />
          </button>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-3">
          {ZONES.map((z) => {
            const lignes = cerveau ? cerveau[z.cle] : []
            return (
              <div
                key={z.cle}
                className="rounded-lg border p-4"
                style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
              >
                <div className="label-tech mb-2 text-[9px] text-orange">{z.titre}</div>
                {lignes.length === 0 ? (
                  <div className="text-[11.5px] text-[#555]">Nothing learned yet.</div>
                ) : (
                  lignes.slice(0, 6).map((l, i) => (
                    <div key={i} className="truncate py-0.5 text-[12px] text-[#c7c7c7]">
                      {'contenu' in l ? l.contenu : ''}
                    </div>
                  ))
                )}
              </div>
            )
          })}
        </div>

        <h3 className="label-tech mb-3 text-[10px] text-[#777777]">DOCUMENTS</h3>
        <div className="mb-3 flex flex-col gap-2">
          {documents.length === 0 && (
            <div className="text-[11.5px] text-[#555]">
              No documents yet — upload your own files to give Jarvis context.
            </div>
          )}
          {documents.map((d) => (
            <div
              key={d.id}
              className="flex items-center gap-2 rounded-lg border px-3 py-2"
              style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}
            >
              <FileText size={13} className="shrink-0 text-[#777777]" />
              <span className="flex-1 truncate text-[12.5px] text-[#c7c7c7]">{d.titre}</span>
              <span className="label-tech text-[8.5px] text-[#555]">
                {Math.max(1, Math.round(d.taille / 1000))}k
              </span>
            </div>
          ))}
        </div>

        <div className="rounded-lg border p-4" style={{ background: 'var(--panel)', borderColor: 'var(--border)' }}>
          <div className="mb-2 flex items-center gap-2">
            <Upload size={12} className="text-orange" />
            <span className="label-tech text-[9px] text-[#c7c7c7]">ADD CONTEXT</span>
          </div>
          <input
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            placeholder="Title (optional)"
            className="mb-2 w-full rounded-md border bg-transparent px-3 py-2 text-[13px] text-[#f5f5f5] outline-none placeholder:text-[#555]"
            style={{ borderColor: 'var(--border)' }}
          />
          <textarea
            value={contenu}
            onChange={(e) => setContenu(e.target.value)}
            placeholder="Paste the content Jarvis should remember…"
            rows={3}
            className="mb-2 w-full resize-none rounded-md border bg-transparent px-3 py-2 text-[13px] text-[#f5f5f5] outline-none placeholder:text-[#555]"
            style={{ borderColor: 'var(--border)' }}
          />
          <div className="flex justify-end">
            <button
              onClick={ajouter}
              disabled={!contenu.trim() || envoi}
              className="label-tech rounded-lg px-4 py-1.5 text-[10px] text-black transition enabled:hover:brightness-110 disabled:opacity-40"
              style={{ background: '#FF6A00' }}
            >
              {envoi ? 'SAVING…' : 'ADD TO BRAIN'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
