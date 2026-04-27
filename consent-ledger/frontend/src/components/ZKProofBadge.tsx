interface Props {
  verified: boolean
  size?: 'sm' | 'md'
}

export function ZKProofBadge({ verified, size = 'sm' }: Props) {
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'
  if (verified) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-semibold ${textSize} bg-emerald-100 text-emerald-800`}>
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
        ZK Verified
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-semibold ${textSize} bg-gray-100 text-gray-500`}>
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
      Pending Proof
    </span>
  )
}
