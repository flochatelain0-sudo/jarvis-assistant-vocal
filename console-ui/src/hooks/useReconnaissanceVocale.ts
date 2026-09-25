import { useCallback, useRef, useState } from 'react'
import { api } from '../lib/api'

// Types minimaux de la Web Speech API (non standardises dans TS).
interface ResultatReco {
  results: { isFinal: boolean; 0: { transcript: string } }[]
  resultIndex: number
}
interface RecoVocale {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  onresult: ((e: ResultatReco) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type ConstrReco = new () => RecoVocale

export interface UseReco {
  disponible: boolean
  actif: boolean
  partiel: string
  erreur: string | null
  basculer: () => void
  demarrer: () => void
  arreter: () => void
}

export function useReconnaissanceVocale(onTranscrit: (texte: string) => void): UseReco {
  const recoRef = useRef<RecoVocale | null>(null)
  const finalRef = useRef('')
  const actifRef = useRef(false)
  const onTranscritRef = useRef(onTranscrit)
  onTranscritRef.current = onTranscrit

  const [actif, setActif] = useState(false)
  const [partiel, setPartiel] = useState('')
  const [erreur, setErreur] = useState<string | null>(null)

  const Constr = (window as unknown as { webkitSpeechRecognition?: ConstrReco; SpeechRecognition?: ConstrReco })
  const disponible = Boolean(Constr?.webkitSpeechRecognition || Constr?.SpeechRecognition)

  const creer = useCallback((): RecoVocale | null => {
    const C = Constr?.webkitSpeechRecognition || Constr?.SpeechRecognition
    if (!C) return null
    const r = new C()
    r.lang = 'fr-FR'
    r.continuous = false
    r.interimResults = true
    r.onresult = (e) => {
      let partielCourant = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) finalRef.current += res[0].transcript
        else partielCourant += res[0].transcript
      }
      setPartiel(partielCourant || finalRef.current)
    }
    r.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed')
        setErreur('micro refuse — autorise le micro dans le navigateur')
      else if (e.error !== 'aborted' && e.error !== 'no-speech')
        setErreur(e.error)
    }
    r.onend = () => {
      const texte = finalRef.current.trim()
      finalRef.current = ''
      setPartiel('')
      setActif(false)
      actifRef.current = false
      if (texte) onTranscritRef.current(texte)
    }
    return r
  }, [Constr])

  const demarrer = useCallback(() => {
    setErreur(null)
    if (actifRef.current || !disponible) return
    finalRef.current = ''
    const r = creer()
    if (!r) return
    recoRef.current = r
    actifRef.current = true
    setActif(true)
    try {
      r.start()
    } catch {
      actifRef.current = false
      setActif(false)
    }
  }, [creer, disponible])

  const arreter = useCallback(() => {
    const r = recoRef.current
    if (!r || !actifRef.current) return
    try {
      r.stop()
    } catch {
      setActif(false)
      actifRef.current = false
    }
  }, [])

  const basculer = useCallback(() => {
    if (actifRef.current) arreter()
    else demarrer()
  }, [arreter, demarrer])

  return { disponible, actif, partiel, erreur, basculer, demarrer, arreter }
}

// Envoie la transcription au chat ecrit de Jarvis (POST /api/operator/message).
// Le backend prononce deja la reponse : rien a faire de plus.
export async function envoyerTranscription(texte: string): Promise<void> {
  await api.envoyer(texte)
}
