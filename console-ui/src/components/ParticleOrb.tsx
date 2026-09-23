import { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * Orbe ZOEY — sphère de particules 3D façon JARVIS (frontend/src/orb.ts).
 *
 * 2000 particules en nuage sphérique, lignes de connexion entre voisines,
 * électrons qui parcourent les connexions pendant la réflexion, tumble de
 * transition au changement d'état. Piloté par l'état réel du HUD :
 * veille | ecoute | reflexion | parole. Thème cyberpunk orange (#FF4500).
 */

export type EtatOrbe = 'veille' | 'ecoute' | 'reflexion' | 'parole'

interface Props {
  etat: EtatOrbe
  /** 0..1 : poussière du micro, fait respirer le nuage même en veille */
  niveau: number
  /** diamètre cible en px */
  taille?: number
}

const N = 2000
const MAX_LIGNES = 8000
const MAX_ELECTRONS = 200

// Palette orange ZOEY par état (plus clair = plus actif).
const COULEURS: Record<EtatOrbe, number> = {
  veille: 0xff6a00,
  ecoute: 0xff7d1a,
  reflexion: 0xffa640,
  parole: 0xff4500,
}

export default function ParticleOrb({ etat, niveau, taille = 430 }: Props) {
  const refCanvas = useRef<HTMLCanvasElement>(null)
  const refs = useRef({ etat, niveau, taille })
  refs.current = { etat, niveau, taille }

  useEffect(() => {
    const canvas = refCanvas.current
    if (!canvas) return

    let destroyed = false
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.setClearColor(0x000000, 0)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 1, 1000)
    camera.position.z = 80

    function dimensionner() {
      const cote = refs.current.taille
      renderer.setSize(cote, cote, false)
      camera.aspect = 1
      camera.updateProjectionMatrix()
    }
    dimensionner()

    // ── Particules ──
    const geo = new THREE.BufferGeometry()
    const pos = new Float32Array(N * 3)
    const vel = new Float32Array(N * 3)
    const phase = new Float32Array(N)
    for (let i = 0; i < N; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = Math.pow(Math.random(), 0.5) * 25
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = r * Math.cos(phi)
      phase[i] = Math.random() * 1000
    }
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    const mat = new THREE.PointsMaterial({
      color: COULEURS.veille,
      size: 0.4,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const points = new THREE.Points(geo, mat)
    scene.add(points)

    // ── Lignes de connexion ──
    const linePos = new Float32Array(MAX_LIGNES * 6)
    const lineGeo = new THREE.BufferGeometry()
    lineGeo.setAttribute('position', new THREE.BufferAttribute(linePos, 3))
    lineGeo.setDrawRange(0, 0)
    const lineMat = new THREE.LineBasicMaterial({
      color: COULEURS.veille,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const lines = new THREE.LineSegments(lineGeo, lineMat)
    scene.add(lines)

    // ── Électrons ──
    const electronGeo = new THREE.BufferGeometry()
    const electronPos = new Float32Array(MAX_ELECTRONS * 3)
    electronGeo.setAttribute('position', new THREE.BufferAttribute(electronPos, 3))
    electronGeo.setDrawRange(0, 0)
    const electronMat = new THREE.PointsMaterial({
      color: 0xffd9a0,
      size: 0.8,
      transparent: true,
      opacity: 1.0,
      sizeAttenuation: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const electrons = new THREE.Points(electronGeo, electronMat)
    scene.add(electrons)

    interface Electron {
      sx: number; sy: number; sz: number
      ex: number; ey: number; ez: number
      t: number
      speed: number
    }
    const actifs: Electron[] = []
    let tauxApparition = 0
    let cibleTaux = 0
    let dernierElectron = 0
    let connexions: { x1: number; y1: number; z1: number; x2: number; y2: number; z2: number }[] = []

    // ── Cibles d'état ──
    let cibleRayon = 25, rayon = 25
    let cibleVitesse = 0.3, vitesse = 0.3
    let cibleLumiere = 0.6, lumiere = 0.6
    let cibleTaille = 0.4, taillePoint = 0.4
    let cibleLignes = 0, lignes = 0
    const distanceLignes = 8
    let spinX = 0, spinY = 0, spinZ = 0
    let energie = 0
    let dernierEtat: EtatOrbe = 'veille'
    let nuageZ = 0, nuageZVel = 0

    const clock = new THREE.Clock()
    const cibleCouleur = new THREE.Color(COULEURS.veille)

    function animer() {
      if (destroyed) return
      requestAnimationFrame(animer)
      const t = clock.getElapsedTime()
      const etat = refs.current.etat
      const pouls = refs.current.niveau

      switch (etat) {
        case 'veille':
          cibleRayon = 28; cibleVitesse = 0.2; cibleLumiere = 0.5; cibleTaille = 0.35
          cibleLignes = 0.15; cibleTaux = 0; break
        case 'ecoute':
          cibleRayon = 22; cibleVitesse = 0.3; cibleLumiere = 0.65; cibleTaille = 0.4
          cibleLignes = 0.4; cibleTaux = 0; break
        case 'reflexion':
          cibleRayon = 16; cibleVitesse = 0.5; cibleLumiere = 0.7; cibleTaille = 0.3
          cibleLignes = 1.0; cibleTaux = 0.015; break
        case 'parole':
          cibleRayon = 18; cibleVitesse = 0.2; cibleLumiere = 0.7; cibleTaille = 0.4
          cibleLignes = 0.8; cibleTaux = 0; break
      }
      // La poussière du micro fait gonfler le nuage, comme la basse du TTS.
      cibleRayon += pouls * 6

      rayon += (cibleRayon - rayon) * 0.02
      vitesse += (cibleVitesse - vitesse) * 0.02
      lumiere += (cibleLumiere - lumiere) * 0.02
      taillePoint += (cibleTaille - taillePoint) * 0.02
      lignes += (cibleLignes - lignes) * 0.02
      tauxApparition += (cibleTaux - tauxApparition) * 0.02

      if (etat !== dernierEtat) { energie = 1.0; dernierEtat = etat }
      energie *= 0.985
      if (energie > 0.05) {
        spinX += energie * 0.012 * Math.sin(t * 1.7)
        spinY += energie * 0.015
        spinZ += energie * 0.008 * Math.cos(t * 1.3)
      }

      // Respiration en profondeur
      let zCible = Math.sin(t * 0.12) * 8 + pouls * 4
      if (etat === 'reflexion') zCible = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6
      else if (etat === 'parole') zCible = Math.sin(t * 0.15) * 6 + pouls * 10
      nuageZVel += (zCible - nuageZ) * 0.008
      nuageZVel *= 0.94
      nuageZ += nuageZVel
      for (const o of [points, lines, electrons]) {
        o.rotation.x = spinX; o.rotation.y = spinY; o.rotation.z = spinZ
        o.position.z = nuageZ
      }

      // ── Mise à jour des particules ──
      const p = geo.getAttribute('position') as THREE.BufferAttribute
      const a = p.array as Float32Array
      for (let i = 0; i < N; i++) {
        const i3 = i * 3
        const x = a[i3], y = a[i3 + 1], z = a[i3 + 2]
        const px = phase[i]
        vel[i3] += Math.sin(t * 0.05 + px) * 0.001 * vitesse
        vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.001 * vitesse
        vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.001 * vitesse
        vel[i3] += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.0008 * vitesse
        vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.0008 * vitesse
        vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.0008 * vitesse
        const dist = Math.sqrt(x * x + y * y + z * z) || 0.01
        const pull = Math.max(0, dist - rayon) * 0.002 + 0.0003
        vel[i3] -= (x / dist) * pull
        vel[i3 + 1] -= (y / dist) * pull
        vel[i3 + 2] -= (z / dist) * pull
        if (pouls > 0.05) {
          vel[i3] += (x / dist) * pouls * 0.02
          vel[i3 + 1] += (y / dist) * pouls * 0.02
          vel[i3 + 2] += (z / dist) * pouls * 0.02
        }
        if (etat === 'parole' && pouls > 0.1) {
          const pulse = Math.sin(t * 8 + px)
          vel[i3] += (x / dist) * pouls * 0.012 * pulse
          vel[i3 + 1] += (y / dist) * pouls * 0.012 * pulse
        }
        vel[i3] *= 0.992; vel[i3 + 1] *= 0.992; vel[i3 + 2] *= 0.992
        a[i3] += vel[i3]; a[i3 + 1] += vel[i3 + 1]; a[i3 + 2] += vel[i3 + 2]
      }
      p.needsUpdate = true

      // ── Lignes ──
      if (lignes > 0.01) {
        const lp = lineGeo.getAttribute('position') as THREE.BufferAttribute
        const la = lp.array as Float32Array
        let nb = 0
        const maxDist = distanceLignes * (1 + pouls * 0.5)
        const maxDistSq = maxDist * maxDist
        const step = Math.max(1, Math.floor(N / 600))
        for (let i = 0; i < N && nb < MAX_LIGNES; i += step) {
          const i3 = i * 3
          const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2]
          for (let j = i + step; j < N && nb < MAX_LIGNES; j += step) {
            const j3 = j * 3
            const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1
            if (dx * dx + dy * dy + dz * dz < maxDistSq) {
              const idx = nb * 6
              la[idx] = x1; la[idx + 1] = y1; la[idx + 2] = z1
              la[idx + 3] = a[j3]; la[idx + 4] = a[j3 + 1]; la[idx + 5] = a[j3 + 2]
              nb++
            }
          }
        }
        lineGeo.setDrawRange(0, nb * 2)
        lp.needsUpdate = true
        lineMat.opacity = lignes * 0.12
        connexions = []
        for (let c = 0; c < Math.min(nb, 500); c++) {
          const ci = c * 6
          connexions.push({
            x1: la[ci], y1: la[ci + 1], z1: la[ci + 2],
            x2: la[ci + 3], y2: la[ci + 4], z2: la[ci + 5],
          })
        }
      } else {
        lineGeo.setDrawRange(0, 0)
        connexions = []
      }

      // ── Électrons (réflexion) ──
      if (connexions.length > 0 && tauxApparition > 0.005) {
        if (actifs.length < 3 && t - dernierElectron > 1.0) {
          const c = connexions[Math.floor(Math.random() * connexions.length)]
          actifs.push({
            sx: c.x1, sy: c.y1, sz: c.z1,
            ex: c.x2, ey: c.y2, ez: c.z2,
            t: 0,
            speed: 0.003 + Math.random() * 0.003,
          })
          dernierElectron = t
        }
      }
      const ep = electronGeo.getAttribute('position') as THREE.BufferAttribute
      const ea = ep.array as Float32Array
      let vivants = 0
      for (let e = actifs.length - 1; e >= 0; e--) {
        const el = actifs[e]
        el.t += el.speed
        if (el.t >= 1) { actifs.splice(e, 1); continue }
        const ei = vivants * 3
        ea[ei] = el.sx + (el.ex - el.sx) * el.t
        ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t
        ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t
        vivants++
      }
      electronGeo.setDrawRange(0, vivants)
      ep.needsUpdate = true

      // ── Couleur et caméra ──
      mat.opacity = lumiere + pouls * 0.08
      mat.size = taillePoint + pouls * 0.05
      cibleCouleur.setHex(COULEURS[etat])
      mat.color.lerp(cibleCouleur, 0.015)
      lineMat.color.lerp(cibleCouleur, 0.015)
      camera.position.x = Math.sin(t * 0.02) * 5
      camera.position.y = Math.cos(t * 0.03) * 3
      camera.lookAt(0, 0, nuageZ * 0.2)
      renderer.render(scene, camera)
    }

    const observateur = new ResizeObserver(dimensionner)
    observateur.observe(canvas)
    animer()

    return () => {
      destroyed = true
      observateur.disconnect()
      renderer.dispose()
      geo.dispose()
      lineGeo.dispose()
      electronGeo.dispose()
      mat.dispose()
      lineMat.dispose()
      electronMat.dispose()
    }
  }, [])

  const cote = taille
  return (
    <canvas
      ref={refCanvas}
      aria-hidden="true"
      style={{
        width: cote,
        height: cote,
        maxWidth: '100%',
        filter: 'drop-shadow(0 0 40px rgba(255,69,0,0.25))',
      }}
    />
  )
}
