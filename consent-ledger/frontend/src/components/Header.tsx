import { useWallet } from '@txnlab/use-wallet-react'
import type { Role, UserView, OrgView } from '../App'

interface Props {
  role: Role
  userView: UserView
  orgView: OrgView
  onUserViewChange: (v: UserView) => void
  onOrgViewChange: (v: OrgView) => void
  onRoleChange: () => void
}

export function Header({ role, userView, orgView, onUserViewChange, onOrgViewChange, onRoleChange }: Props) {
  const { wallets, activeAddress } = useWallet()
  const peraWallet = wallets[0]

  const handleWallet = async () => {
    if (activeAddress) {
      await peraWallet?.disconnect()
    } else {
      await peraWallet?.connect()
    }
  }

  const accentColor = role === 'org' ? 'indigo' : role === 'regulator' ? 'violet' : 'emerald'

  const roleBadge =
    role === 'org'
      ? { label: '🏥 Org', bg: 'bg-indigo-100', text: 'text-indigo-700' }
      : role === 'regulator'
      ? { label: '⚖️ Regulator', bg: 'bg-violet-100', text: 'text-violet-700' }
      : { label: '👤 User', bg: 'bg-emerald-100', text: 'text-emerald-700' }

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo + role badge */}
          <button
            onClick={onRoleChange}
            className="flex items-center gap-2 hover:opacity-75 transition-opacity"
            title="Switch role"
          >
            <span className="text-xl font-bold text-indigo-700">ConsentLedger</span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${roleBadge.bg} ${roleBadge.text}`}>
              {roleBadge.label}
            </span>
          </button>

          {/* Nav tabs */}
          <nav className="flex gap-1 ml-3">
            {role === 'org' && (
              <>
                {([
                  ['request', 'Request Access'],
                  ['granted', 'Granted to Me'],
                  ['forms', 'Form Builder'],
                ] as [OrgView, string][]).map(([v, label]) => (
                  <button
                    key={v}
                    onClick={() => onOrgViewChange(v)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      orgView === v
                        ? 'bg-indigo-100 text-indigo-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </>
            )}
            {role === 'user' && (
              <>
                {([
                  ['grant', 'Grant Consent'],
                  ['consents', 'My Tokens'],
                ] as [UserView, string][]).map(([v, label]) => (
                  <button
                    key={v}
                    onClick={() => onUserViewChange(v)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      userView === v
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </>
            )}
            {role === 'regulator' && (
              <span className="px-3 py-1.5 text-sm font-medium text-violet-700">
                Audit Dashboard
              </span>
            )}
          </nav>
        </div>

        <button
          onClick={handleWallet}
          className={`px-4 py-1.5 rounded-lg text-sm font-semibold transition-colors ${
            activeAddress
              ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              : accentColor === 'indigo'
              ? 'bg-indigo-600 text-white hover:bg-indigo-700'
              : accentColor === 'violet'
              ? 'bg-violet-600 text-white hover:bg-violet-700'
              : 'bg-emerald-600 text-white hover:bg-emerald-700'
          }`}
        >
          {activeAddress
            ? `${activeAddress.slice(0, 6)}…${activeAddress.slice(-4)}`
            : 'Connect Pera Wallet'}
        </button>
      </div>
    </header>
  )
}

