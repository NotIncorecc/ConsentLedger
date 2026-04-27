import { DPDPSectionTag } from './DPDPSectionTag'
import { ZKProofBadge } from './ZKProofBadge'
import { NullifierStatus } from './NullifierStatus'
import { formatExpiry, shortAddr, shortCommitment } from '../utils'
import type { ConsentRecord } from '../utils'

interface Props {
  record: ConsentRecord
  assetId: bigint
  frozen: boolean
  revoking?: boolean
  revokeTxId?: string
  onRevoke?: () => void
  showNullifier?: boolean
}

export function ConsentCard({
  record,
  assetId,
  frozen,
  revoking,
  revokeTxId,
  onRevoke,
  showNullifier = false,
}: Props) {
  const expiryLabel = formatExpiry(record.expiry)
  const isExpired = record.expiry !== 0n && record.expiry < BigInt(Math.floor(Date.now() / 1000))

  const statusColor = frozen
    ? 'border-red-200 bg-red-50'
    : isExpired
    ? 'border-amber-200 bg-amber-50'
    : 'border-emerald-200 bg-emerald-50'

  const statusLabel = frozen ? 'Revoked' : isExpired ? 'Expired' : 'Active'
  const statusTextColor = frozen ? 'text-red-700' : isExpired ? 'text-amber-700' : 'text-emerald-700'

  return (
    <div className={`rounded-xl border p-5 shadow-sm ${statusColor}`}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex flex-wrap gap-2 items-center">
          <ZKProofBadge verified={!frozen && !isExpired} />
          <DPDPSectionTag section={record.dpdpSection} />
          <span className={`text-xs font-bold ${statusTextColor}`}>{statusLabel}</span>
        </div>
        {onRevoke && !frozen && !isExpired && (
          <button
            onClick={onRevoke}
            disabled={revoking}
            className="text-xs font-semibold text-red-600 hover:text-red-800 disabled:opacity-50 transition-colors ml-2"
          >
            {revoking ? 'Revoking…' : 'Revoke'}
          </button>
        )}
      </div>

      {/* Requester */}
      <div className="mb-2">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-0.5">Data Requester</p>
        <p className="font-mono text-sm text-gray-800">{shortAddr(record.requester)}</p>
      </div>

      {/* Commitment */}
      <div className="mb-2">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-0.5">ZK Commitment</p>
        <p className="font-mono text-xs text-gray-600 bg-white border border-gray-200 rounded px-2 py-1">
          {shortCommitment(record.commitment)}
        </p>
        <p className="text-xs text-gray-400 mt-0.5 italic">
          Data type and purpose protected — ZK proof only
        </p>
      </div>

      {/* Nullifier (optional) */}
      {showNullifier && (
        <div className="mb-2">
          <NullifierStatus nullifier={record.nullifier} used={true} />
        </div>
      )}

      {/* Footer */}
      <div className="flex flex-wrap gap-4 mt-3 text-xs text-gray-500">
        <span>
          <span className="font-medium">Expiry:</span> {expiryLabel}
        </span>
        <span>
          <span className="font-medium">ASA:</span>{' '}
          <a
            href={`https://algoexplorer.io/asset/${assetId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:underline font-mono"
          >
            #{assetId.toString()}
          </a>
        </span>
      </div>

      {/* Revoke tx link */}
      {revokeTxId && (
        <div className="mt-2 text-xs text-gray-500">
          Revoked in tx:{' '}
          <a
            href={`https://algoexplorer.io/tx/${revokeTxId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-600 hover:underline font-mono"
          >
            {revokeTxId.slice(0, 8)}…
          </a>
        </div>
      )}
    </div>
  )
}
