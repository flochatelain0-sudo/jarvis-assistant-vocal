import { useEffect, useState } from 'react'

export type Theme = 'sombre' | 'clair'

const CLE = 'jarvis-theme'

export function themeInitial(): Theme {
  try {
    const stocke = localStorage.getItem(CLE)
    if (stocke === 'sombre' || stocke === 'clair') return stocke
  } catch {
    /* localStorage indisponible */
  }
  return 'sombre'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(themeInitial)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem(CLE, theme)
    } catch {
      /* localStorage indisponible */
    }
  }, [theme])

  const basculer = () => setTheme((t) => (t === 'sombre' ? 'clair' : 'sombre'))
  return { theme, basculer }
}
