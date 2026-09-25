interface Props {
  page: number
  nbPages: number
  onPage: (p: number) => void
}

export default function ZoeyBranding(_props: Props) {
  return (
    <h1
      className="label-tech text-orange"
      style={{ fontSize: 13, letterSpacing: '0.7em', textIndent: '0.7em' }}
    >
      JARVIS
    </h1>
  )
}
