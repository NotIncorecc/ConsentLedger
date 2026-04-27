import type { Role } from '../App'

interface Props {
  onSelect: (role: Role) => void
}

export function RolePicker({ onSelect }: Props) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-indigo-50 to-white px-4">
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-extrabold text-indigo-700 tracking-tight mb-2">
          ConsentLedger
        </h1>
        <p className="text-gray-500 text-lg">
          Decentralized consent management on Algorand
        </p>
      </div>

      <p className="text-gray-600 font-medium mb-6 text-sm uppercase tracking-widest">
        Who are you?
      </p>

      <div className="flex flex-col sm:flex-row gap-6 w-full max-w-2xl">
        {/* Organisation card */}
        <button
          onClick={() => onSelect('org')}
          className="flex-1 bg-white border-2 border-indigo-200 hover:border-indigo-500 hover:shadow-lg rounded-2xl p-8 flex flex-col items-center gap-4 transition-all group"
        >
          <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-3xl group-hover:bg-indigo-200 transition-colors">
            🏥
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-gray-800 mb-1">Organisation</p>
            <p className="text-sm text-gray-500">
              Hospital, clinic, or any entity requesting access to user data
            </p>
          </div>
          <span className="mt-2 px-4 py-1.5 rounded-full bg-indigo-600 text-white text-sm font-semibold group-hover:bg-indigo-700 transition-colors">
            Login as Org
          </span>
        </button>

        {/* User card */}
        <button
          onClick={() => onSelect('user')}
          className="flex-1 bg-white border-2 border-emerald-200 hover:border-emerald-500 hover:shadow-lg rounded-2xl p-8 flex flex-col items-center gap-4 transition-all group"
        >
          <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center text-3xl group-hover:bg-emerald-200 transition-colors">
            👤
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-gray-800 mb-1">User</p>
            <p className="text-sm text-gray-500">
              Data owner who grants or revokes access to their records
            </p>
          </div>
          <span className="mt-2 px-4 py-1.5 rounded-full bg-emerald-600 text-white text-sm font-semibold group-hover:bg-emerald-700 transition-colors">
            Login as User
          </span>
        </button>

        {/* Regulator card */}
        <button
          onClick={() => onSelect('regulator')}
          className="flex-1 bg-white border-2 border-violet-200 hover:border-violet-500 hover:shadow-lg rounded-2xl p-8 flex flex-col items-center gap-4 transition-all group"
        >
          <div className="w-16 h-16 rounded-full bg-violet-100 flex items-center justify-center text-3xl group-hover:bg-violet-200 transition-colors">
            ⚖️
          </div>
          <div className="text-center">
            <p className="text-xl font-bold text-gray-800 mb-1">Regulator</p>
            <p className="text-sm text-gray-500">
              Data Protection Board — audit consent records by DPDP Act section
            </p>
          </div>
          <span className="mt-2 px-4 py-1.5 rounded-full bg-violet-600 text-white text-sm font-semibold group-hover:bg-violet-700 transition-colors">
            Audit Dashboard
          </span>
        </button>
      </div>

      <p className="mt-10 text-xs text-gray-400 text-center max-w-sm">
        Connect your Algorand wallet after selecting a role. All consents are stored on-chain as proof of authorisation.
      </p>
    </div>
  )
}
