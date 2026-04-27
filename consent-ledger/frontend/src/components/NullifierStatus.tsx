import { shortCommitment } from '../utils'

interface Props {
  nullifier: string    // hex string
  used: boolean        // true = this nullifier exists on-chain (anti-replay active)
}

export function NullifierStatus({ nullifier, used }: Props) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-gray-400 font-medium uppercase tracking-wider">Nullifier</span>
      <code className="font-mono text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
        {shortCommitment(nullifier)}
      </code>
      {used ? (
        <span className="text-emerald-700 font-semibold">Anti-replay Active</span>
      ) : (
        <span className="text-amber-600 font-semibold">Pending</span>
      )}
    </div>
  )
}
