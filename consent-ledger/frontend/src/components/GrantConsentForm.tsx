import React, { useState } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import algosdk from 'algosdk'
import { ConsentLedgerClient } from '../contracts/ConsentLedgerClient'
import { CONFIG } from '../config'
import { consentBoxName } from '../utils'

const DATA_TYPES = ['Medical', 'KYC', 'Financial', 'Identity', 'Other'] as const
type DataType = (typeof DATA_TYPES)[number]

interface FormState {
  orgAddress: string      // org's Algorand address (the requester)
  orgName: string         // human-readable org name
  dataType: DataType
  purpose: string
  expiry: string
}

interface TxResult {
  txId: string
  assetId: string
}

export function GrantConsentForm() {
  const { transactionSigner, activeAddress, wallets } = useWallet()
  const peraWallet = wallets[0]

  const [form, setForm] = useState<FormState>({
    orgAddress: '',
    orgName: '',
    dataType: 'Medical',
    purpose: '',
    expiry: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TxResult | null>(null)

  const update = (field: keyof FormState, value: string) =>
    setForm((f) => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    if (!activeAddress || !transactionSigner) {
      try {
        await peraWallet?.connect()
        return
      } catch {
        setError('Wallet connection cancelled.')
        return
      }
    }

    if (!form.orgAddress.trim())  { setError('Organisation address is required.'); return }
    if (!form.purpose.trim())     { setError('Purpose is required.'); return }
    if (CONFIG.APP_ID === 0n)     { setError('APP_ID not configured — set VITE_APP_ID in .env'); return }

    if (!algosdk.isValidAddress(form.orgAddress.trim())) {
      setError('Invalid Algorand address for Organisation.')
      return
    }

    const expiryTs = form.expiry
      ? BigInt(Math.floor(new Date(form.expiry).getTime() / 1000))
      : 0n

    const fullPurpose = form.orgName.trim()
      ? `${form.orgName.trim()}: ${form.purpose.trim()}`
      : form.purpose.trim()

    setLoading(true)
    try {
      const algorand = AlgorandClient.testNet()
      algorand.setSigner(activeAddress, transactionSigner)

      const client = algorand.client.getTypedAppClientById(ConsentLedgerClient, {
        appId: CONFIG.APP_ID,
        defaultSender: activeAddress,
      })

      const response = await client.send.grantConsent({
        args: {
          requester: form.orgAddress.trim(),
          dataType: form.dataType,
          purpose: fullPurpose,
          expiry: expiryTs,
        },
        extraFee: (3_000).microAlgo(),
        // Box key is consent_ + sender_bytes(32) + requester_bytes(32) — known before execution
        boxReferences: [{ appId: CONFIG.APP_ID, name: consentBoxName(activeAddress, form.orgAddress.trim()) }],
      })

      setResult({
        txId: response.txIds[0],
        assetId: response.return?.toString() ?? '?',
      })
      setForm({ orgAddress: '', orgName: '', dataType: 'Medical', purpose: '', expiry: '' })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  if (!activeAddress) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="text-5xl mb-4">👤</div>
        <p className="text-lg font-semibold mb-2">Connect your wallet to grant consent</p>
        <p className="text-sm text-gray-400 mb-6">
          You are logged in as a <span className="font-medium text-emerald-600">User</span>. Connect your Pera wallet to authorise data access.
        </p>
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
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-1">Grant Consent to an Organisation</h2>
        <p className="text-gray-500 text-sm">
          Enter the organisation's details below. A consent token (ASA) will be minted on Algorand and stored on-chain as proof of your authorisation.
        </p>
        <div className="mt-3 flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          <span>🔑</span>
          <span>Connected as: <span className="font-mono font-semibold">{activeAddress.slice(0, 8)}…{activeAddress.slice(-6)}</span></span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        {/* Org Address */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Organisation's Algorand Address <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.orgAddress}
            onChange={(e) => update('orgAddress', e.target.value)}
            placeholder="ABCDEF… (58-character Algorand address)"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <p className="text-xs text-gray-400 mt-1">
            The wallet address of the hospital / clinic / organisation requesting your data.
          </p>
        </div>

        {/* Org Name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Organisation Name <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={form.orgName}
            onChange={(e) => update('orgName', e.target.value)}
            placeholder="e.g. Apollo Hospitals"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        {/* Data type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data Type <span className="text-red-500">*</span></label>
          <select
            value={form.dataType}
            onChange={(e) => update('dataType', e.target.value as DataType)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {DATA_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* Purpose */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Purpose of Access <span className="text-red-500">*</span></label>
          <input
            type="text"
            value={form.purpose}
            onChange={(e) => update('purpose', e.target.value)}
            placeholder="e.g. Annual health screening, insurance verification…"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        {/* Expiry */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Consent Expires On <span className="text-gray-400 font-normal">(optional — leave blank for no expiry)</span>
          </label>
          <input
            type="date"
            value={form.expiry}
            onChange={(e) => update('expiry', e.target.value)}
            min={new Date().toISOString().split('T')[0]}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition-colors"
        >
          {loading ? 'Submitting…' : '✓ Approve & Grant Consent'}
        </button>
      </form>

      {result && (
        <div className="mt-4 bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-sm">
          <p className="font-bold text-emerald-800 mb-3 text-base">✓ Consent granted on-chain!</p>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-500">Consent Token ID (ASA)</span>
              <span className="font-mono font-bold text-gray-900">{result.assetId}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-500 shrink-0">Transaction ID</span>
              <span className="font-mono text-indigo-700 text-xs break-all text-right">{result.txId}</span>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3">
            This token is stored on-chain as permanent proof of authorisation. The organisation can verify it at any time.
          </p>
        </div>
      )}
    </div>
  )
}
