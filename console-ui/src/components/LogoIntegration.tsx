// Logos officiels simplifies des providers (SVG inline, pour identification
// du service). Sources : identites visuelles publiques de chaque marque.

interface Props {
  id: string
  nom: string
}

const GOOGLE = (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#4285F4" d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z" />
    <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.27 21.3 7.31 24 12 24z" />
    <path fill="#FBBC05" d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z" />
    <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.27 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z" />
  </svg>
)

const GITHUB = (
  <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true">
    <path fill="#f5f5f5" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A7.995 7.995 0 0 0 16 8c0-4.42-3.58-8-8-8z" />
  </svg>
)

const LINKEDIN = (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#0A66C2" d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.55V9h3.57v11.45z" />
  </svg>
)

const SLACK = (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#E01E5A" d="M5.04 15.16a2.52 2.52 0 1 1-2.52-2.52h2.52v2.52z" />
    <path fill="#E01E5A" d="M6.31 15.16a2.52 2.52 0 0 1 5.04 0v6.32a2.52 2.52 0 1 1-5.04 0v-6.32z" />
    <path fill="#36C5F0" d="M8.83 5.04a2.52 2.52 0 1 1 2.52-2.52v2.52H8.83z" />
    <path fill="#36C5F0" d="M8.83 6.31a2.52 2.52 0 0 1 0 5.04H2.52a2.52 2.52 0 1 1 0-5.04h6.31z" />
    <path fill="#2EB67D" d="M18.96 8.83a2.52 2.52 0 1 1 2.52 2.52h-2.52V8.83z" />
    <path fill="#2EB67D" d="M17.69 8.83a2.52 2.52 0 0 1-5.04 0V2.52a2.52 2.52 0 1 1 5.04 0v6.31z" />
    <path fill="#ECB22E" d="M15.17 18.96a2.52 2.52 0 1 1-2.52 2.52v-2.52h2.52z" />
    <path fill="#ECB22E" d="M15.17 17.69a2.52 2.52 0 0 1 0-5.04h6.32a2.52 2.52 0 1 1 0 5.04h-6.32z" />
  </svg>
)

const NOTION = (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#f5f5f5" d="M4.46 3.16 14.36 2c1.28-.14 1.6-.04 2.4.53l3.15 2.22c.53.37.7.83.7 1.57v12.62c0 1.3-.47 2.06-1.85 2.2L7.34 22.9c-1.16.1-1.72-.35-1.72-1.43V4.57c0-.87.33-1.3 1.26-1.4h.58z" />
    <path fill="#0b0b0d" d="M14.36 2 4.46 3.16h.98l8.92-1.04z" opacity="0" />
    <path fill="#0b0b0d" d="M13.9 9.4c.4 0 .58.11.58.3 0 .73-.05 3.4-.05 3.9 0 1.35-.42 2.65-1.6 2.65-1.15 0-1.53-1.03-1.53-2.3 0-1.6.47-2.5 1.57-2.5.35 0 .63.05.88.16v2.15c-.1-.05-.22-.08-.35-.08-.3 0-.48.2-.48.75 0 .5.17.68.48.68.35 0 .53-.35.53-1.2V9.4h1.06z" />
  </svg>
)

const LINEAR = (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#f5f5f5" d="M12 24 24 12 12 0 0 12 12 24z" />
    <path fill="#5E6AD2" d="M12 24 24 12 12 0v24z" />
  </svg>
)

const LOGOS: Record<string, JSX.Element> = {
  gmail: GOOGLE,
  gcal: GOOGLE,
  gdrive: GOOGLE,
  github: GITHUB,
  linkedin: LINKEDIN,
  slack: SLACK,
  notion: NOTION,
  linear: LINEAR,
}

export default function LogoIntegration({ id, nom }: Props) {
  const logo = LOGOS[id]
  if (!logo) {
    return (
      <span className="text-[15px] font-semibold text-[var(--dim)]">{nom[0]}</span>
    )
  }
  return logo
}
