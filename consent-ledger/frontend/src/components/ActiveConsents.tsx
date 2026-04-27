import { useEffect, useState, useCallback } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import { ConsentLedgerClient } from '../contracts/ConsentLedgerClient'
import { CONFIG } from '../config'
import { decodeConsentRecord, consentBoxName, parseConsentBoxName } from '../utils'
import type { ConsentRecord } from '../utils'
import { ConsentCard } from './ConsentCard'

interface ConsentItem {
  assetId: bigint
  record: ConsentRecord
  frozen: boolean
  revoking: boolean
  revokeTxId?: string
}

export function ActiveConsents() {
  const { transactionSigner, activeAddress, wallets } = useWallet()
  const peraWallet = wallets[0]

  const [items, setItems] = useState<ConsentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

      // Enumerate all app boxes and filter those owned by activeAddress
      const boxesResp = await algod.getApplicationBoxes(appId).do()
      const boxes = boxesResp.boxes ?? []

      const results: ConsentItem[] = []
      for (const box of boxes) {
        const parsed = parseConsentBoxName(box.name)
        if (!parsed || parsed.owner !== activeAddress) continue

        let record: ConsentRecord
        try {
          const boxData = await algod.getApplicationBoxByName(appId, box.name).do()
          record = decodeConsentRecord(boxData.value)
        } catch {
          continue
        }

        let frozen = false
        try {
          const holding = await algod
            .accountAssetInformation(CONFIG.APP_ADDRESS, Number(record.assetId))
            .do()
          frozen = holding.assetHolding?.isFrozen ?? false
        } catch {
          // asset not yet opted-in or other error — treat as active
        }

        results.push({ assetId: record.assetId, record, frozen, revoking: false })
      }
      setItems(results)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [activeAddress])

  useEffect(() => { load() }, [load])

  const handleRevoke = async (requester: string) => {
    if (!activeAddress || !transactionSigner) {
      await peraWallet?.connect()
      return
    }
    const item = items.find((i) => i.record.requester === requester)
    if (!item) return

    setItems((prev) =>
      prev.map((i) => (i.record.requester === requester ? { ...i, revoking: true } : i))
    )
    try {
      const algorand = AlgorandClient.testNet()
      algorand.setSigner(activeAddress, transactionSigner)

      const client = algorand.client.getTypedAppClientById(ConsentLedgerClient, {
        appId: CONFIG.APP_ID,
        defaultSender: activeAddress,
      })

      const boxKey = consentBoxName(activeAddress, requester)

      const response = await client.send.revokeConsent({
        args: { requester },
        extraFee: (1_000).microAlgo(),
        boxReferences: [{ appId: CONFIG.APP_ID, name: boxKey }],
        assetReferences: [item.assetId],
        accountReferences: [CONFIG.APP_ADDRESS],
      })

      setItems((prev) =>
        prev.map((i) =>
          i.record.requester === requester
            ? { ...i, frozen: true, revoking: false, revokeTxId: response.txIds[0] }
            : i
        )
      )
    } catch (err: unknown) {
      setItems((prev) =>
        prev.map((i) => (i.record.requester === requester ? { ...i, revoking: false } : i))
      )
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  if (!activeAddress) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="text-5xl mb-4">👤</div>
        <p className="text-lg font-semibold mb-2">Connect your wallet to view tokens</p>
        <p className="text-sm text-gray-400 mb-6">You are logged in as a <span className="font-medium text-emerald-600">User</span>. Connect your Pera wallet to see your consent tokens.</p>
        <button
          onClick={() => peraWallet?.connect()}
          className="bg-emerald-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-emerald-700 transition-colors"
        >
          Connect Pera Wallet
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">My Consent Tokens</h2>
          <p className="text-gray-500 text-sm">On-chain ZK-committed consent tokens</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="text-sm text-indigo-600 hover:underline disabled:opacity-50"
        >
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">
          {error}
        </p>
      )}

      {loading && items.length === 0 && (
        <div className="text-center py-12 text-gray-400">Loading consent tokens…</div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="text-center py-12 text-gray-400">
          <div className="text-4xl mb-3">🏷️</div>
          <p className="font-medium">No consent tokens found</p>
          <p className="text-sm mt-1">Grant consent using the "Grant Consent" tab.</p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((item) => (
          <ConsentCard
            key={item.record.requester}
            record={item.record}
            assetId={item.assetId}
            frozen={item.frozen}
            revoking={item.revoking}
            revokeTxId={item.revokeTxId}
            onRevoke={() => handleRevoke(item.record.requester)}
            showNullifier
          />
        ))}
      </div>
    </div>
  )
}
