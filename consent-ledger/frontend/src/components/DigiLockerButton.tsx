import { getDigiLockerAuthUrl } from '../lib/zkProver'

interface Props {
  onVerified?: (identitySecret: string) => void
  isVerified?: boolean
}

export function DigiLockerButton({ onVerified, isVerified }: Props) {
  const handleClick = async () => {
    const url = await getDigiLockerAuthUrl()
    if (url === '#digilocker-demo') {
      // Demo mode: simulate successful verification
      const mockSecret = Array.from(crypto.getRandomValues(new Uint8Array(16)))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
      onVerified?.(mockSecret)
      return
    }
    // Real DigiLocker: open in same tab (OAuth redirect will return to /auth/callback)
    window.location.href = url
  }

  if (isVerified) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm font-semibold text-emerald-700">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        DigiLocker Verified
      </div>
    )
  }

  return (
    <button
      onClick={handleClick}
      className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-colors"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
      Verify with DigiLocker
    </button>
  )
}
