import { useEffect, useMemo, useRef, useState } from 'react'
import { Search, Plus, X, Check, MoreHorizontal, Loader, ExternalLink } from 'lucide-react'
import {
  api,
  type IntegrationDef,
  type ConnexionIntegration,
} from '../lib/api'
import LogoIntegration from './LogoIntegration'

interface Props {
  onFermer: () => void
  oauthResultat?: string | null
}

type Onglet = 'browse' | 'connected'

// Ou creer l'application OAuth chez chaque provider (guide setup reel).
const SETUP_URLS: Record<string, string> = {
  gmail: 'https://console.cloud.google.com/apis/credentials',
  gcal: 'https://console.cloud.google.com/apis/credentials',
  gdrive: 'https://console.cloud.google.com/apis/credentials',
  github: 'https://github.com/settings/developers',
  linkedin: 'https://www.linkedin.com/developers/apps',
  slack: 'https://api.slack.com/apps',
  notion: 'https://www.notion.so/my-integrations',
  linear: 'https://linear.app/settings/api',
  outlook: 'https://portal.azure.com',
  hubspot: 'https://developers.hubspot.com',
}

const ERREURS_OAUTH: Record<string, string> = {
  cancelled: 'Connection cancelled.',
  state: 'Invalid connection state — restart the connection.',
  failed: 'Unable to connect this account.',
  connected: 'Connected successfully.',
}

export default function IntegrationsPanel({ onFermer, oauthResultat }: Props) {
  const [recherche, setRecherche] = useState('')
  const [onglet, setOnglet] = useState<Onglet>('browse')
  const [categorie, setCategorie] = useState('ALL')
  const [catalogue, setCatalogue] = useState<IntegrationDef[] | null>(null)
  const [categories, setCategories] = useState<string[]>(['ALL'])
  const [connectes, setConnectes] = useState<Set<string>>(new Set())
  const [enCours, setEnCours] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [detail, setDetail] = useState<IntegrationDef | null>(null)
  const [connexionDetail, setConnexionDetail] = useState<ConnexionIntegration | null>(null)
  const [menuOuvert, setMenuOuvert] = useState<string | null>(null)
  const rechercheRef = useRef<HTMLInputElement>(null)

  const rafraichir = async () => {
    const c = await api.catalogueIntegrations()
    if (c && c.integrations) {
      setCatalogue(c.integrations)
      setCategories(c.categories)
      setConnectes(new Set(c.integrations.filter((i) => i.connected).map((i) => i.id)))
    }
  }

  useEffect(() => {
    rafraichir()
  }, [])

  useEffect(() => {
    if (oauthResultat && ERREURS_OAUTH[oauthResultat]) {
      setMessage(ERREURS_OAUTH[oauthResultat])
      if (oauthResultat === 'connected') rafraichir()
    }
  }, [oauthResultat])

  // debounce de la recherche (catalogue borne mais confortable)
  const [rechercheAppliquee, setRechercheAppliquee] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setRechercheAppliquee(recherche.trim().toLowerCase()), 200)
    return () => clearTimeout(t)
  }, [recherche])

  const compteurs = useMemo(() => {
    const m: Record<string, number> = { ALL: catalogue?.length ?? 0 }
    for (const c of categories.slice(1)) {
      m[c] = catalogue?.filter((i) => i.category === c).length ?? 0
    }
    return m
  }, [catalogue, categories])

  const visibles = useMemo(() => {
    if (!catalogue) return []
    let liste = catalogue
    if (onglet === 'connected') liste = liste.filter((i) => i.connected)
    if (categorie !== 'ALL') liste = liste.filter((i) => i.category === categorie)
    if (rechercheAppliquee) {
      liste = liste.filter(
        (i) =>
          i.name.toLowerCase().includes(rechercheAppliquee) ||
          i.description.toLowerCase().includes(rechercheAppliquee) ||
          i.category.toLowerCase().includes(rechercheAppliquee) ||
          i.capabilities.some((c) => c.toLowerCase().includes(rechercheAppliquee)),
      )
    }
    return liste
  }, [catalogue, onglet, categorie, rechercheAppliquee])

  const connecter = async (id: string) => {
    if (enCours) return
    setEnCours(id)
    setMessage(null)
    const r = await api.connecterIntegration(id)
    setEnCours(null)
    if (r && r.ok && r.authorizationUrl) {
      window.location.href = r.authorizationUrl
    } else {
      setMessage((r && r.message) || 'Unable to connect this account.')
    }
  }

  const deconnecter = async (id: string) => {
    setMenuOuvert(null)
    const r = await api.deconnecterIntegration(id)
    if (r && r.ok) {
      setMessage(`${id} disconnected.`)
      await rafraichir()
    } else {
      setMessage((r && r.message) || 'Unable to disconnect.')
    }
  }

  const ouvrirDetail = async (integ: IntegrationDef) => {
    setDetail(integ)
    setConnexionDetail(null)
    if (integ.connected) {
      const r = await api.statutIntegration(integ.id)
      if (r && r.connection) setConnexionDetail(r.connection)
    }
  }

  const carte = (integ: IntegrationDef) => {
    const deja = connectes.has(integ.id)
    const occupe = enCours === integ.id
    return (
      <div
        key={integ.id}
        onClick={() => ouvrirDetail(integ)}
        className="group cursor-pointer rounded-xl border p-4 transition-all duration-200 hover:-translate-y-0.5"
        style={{
          background: 'linear-gradient(180deg, #0B0B0D 0%, #090909 100%)',
          borderColor: deja ? 'rgba(32,232,120,0.25)' : 'rgba(255,255,255,0.08)',
          boxShadow: deja ? '0 0 22px rgba(32,232,120,0.07)' : 'none',
        }}
      >
        <div className="flex items-start justify-between">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg border"
            style={{ borderColor: 'var(--border)', background: 'var(--panel-light)' }}
          >
            <LogoIntegration id={integ.id} nom={integ.name} />
          </div>
          {deja ? (
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setMenuOuvert(menuOuvert === integ.id ? null : integ.id)
                }}
                aria-label="Manage connection"
                className="rounded-md p-1 text-[var(--muted)] transition hover:bg-white/5 hover:text-[var(--text)]"
              >
                <MoreHorizontal size={14} />
              </button>
              {menuOuvert === integ.id && (
                <div
                  className="absolute right-0 top-7 z-30 w-32 rounded-lg border py-1"
                  style={{ background: 'var(--modal)', borderColor: 'var(--border)' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => setMenuOuvert(null)}
                    className="block w-full px-3 py-1.5 text-left text-[11.5px] text-[var(--dim)] transition hover:bg-white/5"
                  >
                    Manage
                  </button>
                  <button
                    onClick={() => deconnecter(integ.id)}
                    className="block w-full px-3 py-1.5 text-left text-[11.5px] text-[var(--red)] transition hover:bg-white/5"
                  >
                    Disconnect
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                if (integ.enabled) connecter(integ.id)
                else ouvrirDetail(integ)
              }}
              disabled={occupe}
              aria-label={`Connect ${integ.name}`}
              className="flex h-6 w-6 items-center justify-center rounded-md border transition-all"
              style={{
                borderColor: integ.enabled ? 'var(--border-orange)' : 'rgba(255,255,255,0.10)',
                background: integ.enabled ? 'rgba(255,106,0,0.06)' : 'transparent',
              }}
            >
              {occupe ? (
                <Loader size={11} className="animate-spin text-orange" />
              ) : integ.enabled ? (
                <Plus size={12} className="text-orange" />
              ) : (
                <span className="label-tech text-[7px] text-[var(--placeholder)]">SETUP</span>
              )}
            </button>
          )}
        </div>
        <div className="mt-3 flex items-center gap-1.5">
          <span className="text-[13.5px] font-medium text-[var(--text)]">{integ.name}</span>
          {deja && <Check size={11} className="text-green" />}
        </div>
        <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-[var(--muted)]">
          {integ.status === 'setup_required'
            ? 'Available — setup required'
            : integ.description}
        </p>
      </div>
    )
  }

  return (
    <div className="absolute inset-x-0 bottom-0 top-0 z-20 flex flex-col overflow-hidden"
      style={{ background: 'var(--bg)' }}>
      {/* header */}
      <div className="px-8 pt-8" style={{ marginTop: 60 }}>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="label-tech text-orange" style={{ fontSize: 22, letterSpacing: '0.22em' }}>
              INTEGRATIONS
            </h1>
            <p className="mt-1.5 text-[13.5px] text-[var(--muted)]">
              Connect your platforms — Zoey will handle the rest.
            </p>
          </div>
          <button onClick={onFermer} aria-label="Fermer" className="mt-2 text-[var(--muted)] transition hover:text-[var(--text)]">
            <X size={16} />
          </button>
        </div>

        {/* recherche + tabs */}
        <div className="mt-6 flex items-center gap-4">
          <div
            className="flex flex-1 items-center gap-2.5 rounded-xl border px-4 py-3"
            style={{ background: 'var(--panel-glass)', borderColor: 'var(--border)' }}
          >
            <Search size={15} className="shrink-0 text-[var(--muted)]" />
            <input
              ref={rechercheRef}
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Search integrations..."
              className="flex-1 bg-transparent text-[14px] text-[var(--text)] outline-none placeholder:text-[var(--placeholder)]"
            />
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              onClick={() => setOnglet('browse')}
              className="label-tech rounded-lg px-4 py-2.5 text-[10px] transition"
              style={{
                color: onglet === 'browse' ? '#FF8500' : '#777777',
                background: onglet === 'browse' ? 'rgba(255,106,0,0.10)' : 'transparent',
                boxShadow: onglet === 'browse' ? 'inset 0 0 0 1px var(--accent-ring)' : 'inset 0 0 0 1px var(--border)',
              }}
            >
              BROWSE
            </button>
            <button
              onClick={() => setOnglet('connected')}
              className="label-tech rounded-lg px-4 py-2.5 text-[10px] transition"
              style={{
                color: onglet === 'connected' ? '#FF8500' : '#777777',
                background: onglet === 'connected' ? 'rgba(255,106,0,0.10)' : 'transparent',
                boxShadow: onglet === 'connected' ? 'inset 0 0 0 1px var(--accent-ring)' : 'inset 0 0 0 1px var(--border)',
              }}
            >
              CONNECTED ({connectes.size})
            </button>
          </div>
        </div>

        {/* categories */}
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
          {categories.map((c) => {
            const actif = categorie === c
            return (
              <button
                key={c}
                onClick={() => setCategorie(c)}
                className="label-tech shrink-0 rounded-full border px-3.5 py-1.5 text-[9px] transition"
                style={{
                  color: actif ? '#FF8500' : '#777777',
                  borderColor: actif ? 'rgba(255,106,0,0.45)' : 'rgba(255,255,255,0.08)',
                  background: actif ? 'rgba(255,106,0,0.07)' : 'rgba(11,11,13,0.9)',
                  boxShadow: actif ? '0 0 18px rgba(255,106,0,0.10)' : 'none',
                }}
              >
                {c} {compteurs[c] ?? 0}
              </button>
            )
          })}
        </div>
      </div>

      {/* message OAuth */}
      {message && (
        <div className="mx-8 mt-4 rounded-lg border px-4 py-2.5"
          style={{
            borderColor: message.includes('success') || message.includes('Connected')
              ? 'rgba(32,232,120,0.35)' : 'rgba(255,106,0,0.35)',
            background: 'var(--panel-glass)',
          }}>
          <span className="text-[12.5px] text-[var(--dim)]">{message}</span>
        </div>
      )}

      {/* grille */}
      <div className="flex-1 overflow-y-auto px-8 pb-8 pt-5">
        {catalogue === null ? (
          <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-4 max-lg:grid-cols-3 max-md:grid-cols-2 max-sm:grid-cols-1">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="h-[118px] animate-pulse rounded-xl border"
                style={{ background: 'var(--panel)', borderColor: 'var(--border)' }} />
            ))}
          </div>
        ) : visibles.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <span className="text-[14px] text-[var(--muted)]">
              {onglet === 'connected'
                ? 'No integrations connected yet.'
                : 'No integration matches your search.'}
            </span>
            <span className="text-[12px] text-[var(--placeholder)]">
              {onglet === 'connected'
                ? 'Connect a platform to get started.'
                : 'Try a different keyword or category.'}
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-4 max-xl:grid-cols-4 max-lg:grid-cols-3 max-md:grid-cols-2 max-sm:grid-cols-1">
            {visibles.map(carte)}
          </div>
        )}
      </div>

      {/* modal detail */}
      {detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'var(--overlay)', backdropFilter: 'blur(6px)' }}
          onClick={() => setDetail(null)}
        >
          <div
            className="w-[420px] rounded-xl border p-6"
            style={{
              background: 'var(--modal)',
              borderColor: 'var(--border-orange)',
              boxShadow: '0 0 44px rgba(255,106,0,0.16), 0 20px 60px rgba(0,0,0,0.6)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-lg border"
                  style={{ borderColor: 'var(--border)', background: 'var(--panel-light)' }}
                >
                  <LogoIntegration id={detail.id} nom={detail.name} />
                </div>
                <h2 className="label-tech text-[11px] text-[var(--text)]">{detail.name.toUpperCase()}</h2>
              </div>
              <button onClick={() => setDetail(null)} aria-label="Fermer" className="text-[var(--muted)] transition hover:text-[var(--text)]">
                <X size={15} />
              </button>
            </div>
            <p className="mb-4 text-[13.5px] leading-relaxed text-[var(--dim)]">{detail.description}</p>
            <h3 className="label-tech mb-2 text-[9px] text-[var(--muted)]">CAPABILITIES</h3>
            <div className="mb-4 flex flex-col gap-1.5">
              {detail.capabilities.map((c) => (
                <div key={c} className="flex items-center gap-2 text-[12.5px] text-[var(--dim)]">
                  <Check size={11} className="text-green" /> {c}
                </div>
              ))}
            </div>
            <h3 className="label-tech mb-2 text-[9px] text-[var(--muted)]">PERMISSIONS</h3>
            <div className="mb-5 flex flex-col gap-1">
              {detail.scopes.map((s) => (
                <span key={s} className="text-[11px] text-[var(--muted)]">• {s}</span>
              ))}
            </div>
            {detail.connected ? (
              <div className="flex flex-col gap-2">
                {connexionDetail && (
                  <div className="mb-1 text-[11.5px] text-[var(--muted)]">
                    Account: <span className="text-[var(--dim)]">{connexionDetail.providerAccountId || '—'}</span>
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => setDetail(null)}
                    className="label-tech flex-1 rounded-lg border py-2.5 text-[10px] text-[var(--dim)] transition hover:border-orange/40"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    MANAGE CONNECTION
                  </button>
                  <button
                    onClick={() => {
                      deconnecter(detail.id)
                      setDetail(null)
                    }}
                    className="label-tech flex-1 rounded-lg border py-2.5 text-[10px] text-[var(--red)] transition hover:bg-white/5"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    DISCONNECT
                  </button>
                </div>
              </div>
            ) : detail.enabled ? (
              <button
                onClick={() => connecter(detail.id)}
                disabled={enCours === detail.id}
                className="label-tech flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-[10px] text-[var(--bg2)] transition enabled:hover:brightness-110 disabled:opacity-50"
                style={{ background: '#FF6A00', boxShadow: '0 0 16px rgba(255,106,0,0.35)' }}
              >
                {enCours === detail.id ? (
                  <>
                    <Loader size={12} className="animate-spin" /> CONNECTING…
                  </>
                ) : (
                  `CONNECT ${detail.name.toUpperCase()}`
                )}
              </button>
            ) : (
              <div className="flex flex-col gap-2">
                <div className="rounded-lg border px-4 py-2.5 text-[12px] leading-relaxed text-[var(--muted)]"
                  style={{ borderColor: 'var(--border)' }}>
                  Available — setup required. Create the OAuth app at the provider
                  (button below), add the redirect URI
                  {' '}
                  <code className="text-[10.5px] text-[var(--dim)]">
                    http://127.0.0.1:8790/api/integrations/{detail.id}/callback
                  </code>
                  , then paste the client ID and secret into the
                  {' '}<span className="text-[var(--dim)]">integrations.{detail.id}</span>{' '}
                  section of config.yaml and restart.
                </div>
                {SETUP_URLS[detail.id] && (
                  <a
                    href={SETUP_URLS[detail.id]}
                    target="_blank"
                    rel="noreferrer"
                    className="label-tech flex items-center justify-center gap-1.5 rounded-lg border py-2 text-[9.5px] text-[var(--dim)] transition hover:text-orange"
                    style={{ borderColor: 'var(--border)' }}
                  >
                    <ExternalLink size={10} /> CREATE OAUTH APP AT {detail.name.toUpperCase()}
                  </a>
                )}
                {detail.documentationUrl && (
                  <a
                    href={detail.documentationUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="label-tech flex items-center justify-center gap-1.5 text-[9.5px] text-[var(--muted)] transition hover:text-orange"
                  >
                    <ExternalLink size={10} /> PROVIDER DOCUMENTATION
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
