import { useEffect, useRef } from 'react'

interface Props {
  actif: boolean // ecoute : le champ de particules devient plus agite
  niveau: number // 0..1 : poussiere du micro, fait vibrer la surface
  taille?: number // diametre cible en px (mobile plus petit)
}

interface Particule {
  // point 3D sur la sphere (Fibonacci : repartition uniforme)
  x: number
  y: number
  z: number
  phase: number // deplacement individuel
  vitesse: number
}

const NOMBRE = 15000

function fibonacci(i: number, n: number): Particule {
  const phi = Math.acos(1 - (2 * (i + 0.5)) / n)
  const theta = Math.PI * (1 + Math.sqrt(5)) * i
  return {
    x: Math.cos(theta) * Math.sin(phi),
    y: Math.cos(phi),
    z: Math.sin(theta) * Math.sin(phi),
    phase: Math.random() * Math.PI * 2,
    vitesse: 0.4 + Math.random() * 0.9,
  }
}

export default function ParticleOrb({ actif, niveau, taille = 420 }: Props) {
  const refCanvas = useRef<HTMLCanvasElement>(null)
  const refs = useRef({ actif, niveau })
  refs.current = { actif, niveau }

  useEffect(() => {
    const canvas = refCanvas.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const cote = taille
    canvas.width = cote * dpr
    canvas.height = cote * dpr
    ctx.scale(dpr, dpr)

    const particules: Particule[] = []
    for (let i = 0; i < NOMBRE; i++) particules.push(fibonacci(i, NOMBRE))

    const cx = cote / 2
    const cy = cote / 2
    const rayon = cote * 0.31
    let rotation = 0
    let raf = 0
    let niveauLisse = 0

    const dessiner = (t: number) => {
      const { actif: ecoute, niveau: mic } = refs.current
      rotation += 0.0016 + (ecoute ? 0.0011 : 0) + mic * 0.004
      niveauLisse += (mic - niveauLisse) * 0.25

      // leger allongement vertical + respiration
      const respiration = 1 + 0.02 * Math.sin(t / 1400) + niveauLisse * 0.045
      const scaleY = 1.06 * respiration
      const scaleX = 0.94 / respiration

      ctx.clearRect(0, 0, cote, cote)
      ctx.globalCompositeOperation = 'lighter'

      const cosR = Math.cos(rotation)
      const sinR = Math.sin(rotation)
      const agitation = ecoute ? 1 : 0.55

      // halo externe discret
      const halo = ctx.createRadialGradient(cx, cy, rayon * 0.4, cx, cy, rayon * 1.7)
      halo.addColorStop(0, 'rgba(255,106,0,0.10)')
      halo.addColorStop(0.55, 'rgba(255,80,0,0.045)')
      halo.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = halo
      ctx.fillRect(0, 0, cote, cote)

      for (let i = 0; i < NOMBRE; i++) {
        const p = particules[i]
        // rotation autour de l'axe Y + tremble du micro
        const x1 = p.x * cosR - p.z * sinR
        const z1 = p.x * sinR + p.z * cosR
        const tremble = Math.sin(t / 90 + p.phase) * niveauLisse * 5.5
        const sc = rayon * (1 + 0.012 * Math.sin(t / 700 + p.phase) * agitation)

        const px = cx + x1 * sc * scaleX + tremble
        const py = cy + p.y * sc * scaleY + tremble * 0.6
        const profondeur = (z1 + 1) / 2 // 0 derriere, 1 devant

        // profondeur : les particules arrieres sont sombres et fines
        const alpha = 0.04 + profondeur * profondeur * 0.5
        const taillePoint = 0.55 + profondeur * 0.85

        ctx.fillStyle = `rgba(${255},${90 + Math.round(profondeur * 80)},${Math.round(
          profondeur * 26,
        )},${alpha.toFixed(3)})`
        ctx.fillRect(px, py, taillePoint, taillePoint)
      }

      // coeur legerement plus dense (quelques particules brillantes en plus)
      for (let i = 0; i < 60; i++) {
        const a = t / 2000 + (i * Math.PI * 2) / 60
        const px = cx + Math.cos(a) * rayon * 0.32 * scaleX
        const py = cy + Math.sin(a) * rayon * 0.32 * scaleY
        ctx.fillStyle = 'rgba(255,180,110,0.5)'
        ctx.fillRect(px, py, 1.4, 1.4)
      }

      ctx.globalCompositeOperation = 'source-over'
      raf = requestAnimationFrame(dessiner)
    }
    raf = requestAnimationFrame(dessiner)
    return () => cancelAnimationFrame(raf)
  }, [taille])

  return (
    <canvas
      ref={refCanvas}
      style={{ width: taille, height: taille }}
      aria-label="Orbe de particules — visualisation de Jarvis"
    />
  )
}
