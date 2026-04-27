import { useEffect, useState, useCallback } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import { CONFIG } from '../config'
import { decodeConsentRecord, parseConsentBoxName, shortAddr } from '../utils'
import type { ConsentRecord } from '../utils'
import type { OrgView } from '../App'
import { ConsentCard } from './ConsentCard'

interface GrantedConsent {
  assetId: bigint
  record: ConsentRecord
  revoked: boolean
}

interface Props {
  view: Exclude<OrgView, 'forms'>
}

export function OrgConsents({ view }: Props) {
  const { activeAddress, wallets } = useWallet()
  const peraWallet = wallets[0]

  const [items, setItems] = useState<GrantedConsent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const load = useCallback(async () => {
    if (!activeAddress) return
    if (CONFIG.APP_ID === 0n) {
      setError('APP_ID not configured — set VITE_APP_ID in .env')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const algorand = AlgorandClient.testNet()
      const algod = algorand.client.algod
      const appId = Number(CONFIG.APP_ID)

      const boxesResp = await algod.getApplicationBoxes(appId).do()
      const boxes = boxesResp.boxes ?? []

      const matched: GrantedConsent[] = []
      for (const box of boxes) {
        const parsed = parseConsentBoxName(box.name)
        if (!parsed || parsed.requester !== activeAddress) continue

        let record: ConsentRecord
        try {
          const boxData = await algod.getApplicationBoxByName(appId, box.name).do()
          record = decodeConsentRecord(boxData.value)
        } catch {
          continue
        }

        const assetId = record.assetId

        let revoked = false
        try {
          const holding = await algod
            .accountAssetInformation(CONFIG.APP_ADDRESS, Number(assetId))
            .do()
          revoked = holding.assetHolding?.isFrozen ?? false
        } catch {
          // ignore
        }

        matched.push({ assetId, record, revoked })
      }

      setItems(matched)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [activeAddress])

  useEffect(() => {
    if (view === 'granted') load()
  }, [load, view])

  const handleCopy = () => {
    if (!activeAddress) return
    navigator.clipboard.writeText(activeAddress)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!activeAddress) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="text-5xl mb-4">🏥</div>
        <p className="text-lg font-semibold mb-2">Connect your organisation wallet</p>
        <p className="text-sm text-gray-400 mb-6">
          You are logged in as an <span className="font-medium text-indigo-600">Organisation</span>. Connect your Pera wallet to continue.
        </p>
        <button
          onClick={() => peraWallet?.connect()}
          className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-indigo-700 transition-colors"
        >
          Connect Pera Wallet
        </button>
      </div>
    )
  }

  if (view === 'request') {
    return (
      <div>
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-1">Request Data Access</h2>
          <p className="text-gray-500 text-sm">
            Share your organisation's Algorand address with the data owner (user). They will use it to grant you consent on-chain.
          </p>
        </div>

        {/* Connected org info */}
        <div className="bg-white border border-indigo-100 rounded-xl p-6 shadow-sm mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center text-xl">🏥</div>
            <div>
              <p className="font-semibold text-gray-800">Your Organisation Wallet</p>
              <p className="text-xs text-gray-400">Connected to LocalNet</p>
            </div>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-3">
            <p className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wider">Algorand Address</p>
            <p className="font-mono text-sm text-gray-900 break-all">{activeAddress}</p>
          </div>

          <button
            onClick={handleCopy}
            className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
              copied
                ? 'bg-green-100 text-green-700 border border-green-200'
                : 'bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100'
            }`}
          >
            {copied ? '✓ Copied!' : '📋 Copy Address'}
          </button>
        </div>

        {/* Instructions */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm">
          <p className="font-bold text-amber-800 mb-3">How to request consent:</p>
          <ol className="space-y-2 text-amber-900">
            <li className="flex gap-2">
              <span className="font-bold shrink-0">1.</span>
              <span>Copy your organisation address above and share it with the data owner (the user/patient).</span>
            </li>
            <li className="flex gap-2">
              <span className="font-bold shrink-0">2.</span>
              <span>The user logs in as <strong>User</strong>, enters your address, selects the data type and purpose, then clicks <strong>Approve & Grant Consent</strong>.</span>
            </li>
            <li className="flex gap-2">
              <span className="font-bold shrink-0">3.</span>
              <span>A consent token (ASA) is minted on-chain. Come back to <strong>Granted to Me</strong> to view all consents granted to your address.</span>
            </li>
          </ol>
        </div>
      </div>
    )
  }

  // view === 'granted'
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Consents Granted to You</h2>
          <p className="text-gray-500 text-sm">
            On-chain consent tokens where your address is the authorised requester
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="text-sm text-indigo-600 hover:underline disabled:opacity-50"
        >
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2 text-sm text-indigo-800">
        Showing consents for: <span className="font-mono font-semibold">{shortAddr(activeAddress)}</span>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
          {error}
        </p>
      )}

      {loading && items.length === 0 && (
        <div className="text-center py-12 text-gray-400">Scanning on-chain consent records…</div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="text-center py-12 text-gray-400">
          <p className="mb-2">No consents granted to your address yet.</p>
          <p className="text-xs">Share your address with a user so they can grant you access.</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((item) => (
          <ConsentCard
            key={item.assetId.toString()}
            record={item.record}
            assetId={item.assetId}
            frozen={item.revoked}
            showNullifier
          />
        ))}
      </div>
    </div>
  )
}
