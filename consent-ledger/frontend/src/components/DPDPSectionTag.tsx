import { getDPDPSection } from '../lib/circuitRegistry'

interface Props {
  section: number
  size?: 'sm' | 'md'
}

export function DPDPSectionTag({ section, size = 'sm' }: Props) {
  const meta = getDPDPSection(section)
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-semibold ${textSize} ${meta.color} ${meta.textColor}`}>
      {meta.name}
    </span>
  )
}
