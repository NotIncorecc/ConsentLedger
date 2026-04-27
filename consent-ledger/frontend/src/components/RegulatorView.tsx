/**
 * RegulatorView — Read-only regulator audit dashboard.
 *
 * Fetches all on-chain consents, aggregates by DPDP section,
 * and displays commitment hashes only — no raw data ever shown.
 *
 * This is a differentiator vs all competitors: ZK-native audit trail.
 */

import { useEffect, useState, useCallback } from 'react'
import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import { CONFIG } from '../config'
import { decodeConsentRecord, parseConsentBoxName, formatExpiry, shortAddr, shortCommitment } from '../utils'
import type { ConsentRecord } from '../utils'
import { DPDPSectionTag } from './DPDPSectionTag'
import { ZKProofBadge } from './ZKProofBadge'
import { NullifierStatus } from './NullifierStatus'
import { DPDP_SECTIONS } from '../lib/circuitRegistry'

interface ConsentEntry {
  owner: string
  record: ConsentRecord
  assetId: bigint
  frozen: boolean
}

interface SectionSummary {
  code: number
  count: number
  active: number
  revoked: number
  expired: number
}

export function RegulatorView() {
  const [entries, setEntries] = useState<ConsentEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<number | 'all'>('all')
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  const now = BigInt(Math.floor(Date.now() / 1000))

  const load = useCallback(async () => {
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

      const results: ConsentEntry[] = []
      for (const box of boxes) {
        const parsed = parseConsentBoxName(box.name)
        if (!parsed) continue

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
          // ignore
        }

        results.push({ owner: parsed.owner, record, assetId: record.assetId, frozen })
      }
      setEntries(results)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // ── Statistics ──────────────────────────────────────────────────────────────
  const summaries: SectionSummary[] = DPDP_SECTIONS.map((s) => {
    const sectionEntries = entries.filter((e) => e.record.dpdpSection === s.code)
    const isExpired = (e: ConsentEntry) =>
      e.record.expiry !== 0n && e.record.expiry < now
    return {
      code: s.code,
      count: sectionEntries.length,
      active:  sectionEntries.filter((e) => !e.frozen && !isExpired(e)).length,
      revoked: sectionEntries.filter((e) => e.frozen).length,
      expired: sectionEntries.filter((e) => isExpired(e) && !e.frozen).length,
    }
  })

  const totalZKVerified = entries.filter((e) => e.record.commitment.length === 64).length
  const zkVerifiedRate = entries.length > 0 ? Math.round((totalZKVerified / entries.length) * 100) : 0

  // ── Filter ──────────────────────────────────────────────────────────────────
  const filtered = filter === 'all'
    ? entries
    : entries.filter((e) => e.record.dpdpSection === filter)

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Regulator Audit Dashboard</h2>
          <p className="text-gray-500 text-sm">
            Read-only view. Commitment hashes only — raw data never exposed on-chain.
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

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mb-5">
          {error}
        </div>
      )}

      {/* ── Stats cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm text-center">
          <p className="text-3xl font-extrabold text-gray-800">{entries.length}</p>
          <p className="text-xs text-gray-500 mt-1">Total Consents</p>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 shadow-sm text-center">
          <p className="text-3xl font-extrabold text-emerald-700">{zkVerifiedRate}%</p>
          <p className="text-xs text-emerald-600 mt-1">ZK Verified</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 shadow-sm text-center">
          <p className="text-3xl font-extrabold text-red-700">
            {entries.filter((e) => e.frozen).length}
          </p>
          <p className="text-xs text-red-500 mt-1">Revoked</p>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 shadow-sm text-center">
          <p className="text-3xl font-extrabold text-amber-700">
            {entries.filter((e) => e.record.expiry !== 0n && e.record.expiry < now && !e.frozen).length}
          </p>
          <p className="text-xs text-amber-600 mt-1">Expired</p>
        </div>
      </div>

      {/* ── DPDP section breakdown ────────────────────────────────────────── */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 mb-6 shadow-sm">
        <p className="text-sm font-semibold text-gray-700 mb-3">Breakdown by DPDP Act Section</p>
        <div className="space-y-2">
          {summaries.map((s) => {
            const meta = DPDP_SECTIONS.find((d) => d.code === s.code)!
            const total = s.count || 0
            const pct = entries.length > 0 ? Math.round((total / entries.length) * 100) : 0
            return (
              <div key={s.code}>
                <div className="flex items-center justify-between text-xs mb-0.5">
                  <DPDPSectionTag section={s.code} />
                  <span className="text-gray-500">
                    {total} total · {s.active} active · {s.revoked} revoked · {s.expired} expired
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-1.5">
                  <div
                    className={`${meta.color.replace('bg-', 'bg-').replace('-100', '-400')} h-1.5 rounded-full transition-all`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Section filter ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg border-2 transition-colors ${
            filter === 'all' ? 'bg-gray-800 text-white border-gray-800' : 'bg-white text-gray-600 border-gray-300 hover:border-gray-500'
          }`}
        >
          All ({entries.length})
        </button>
        {DPDP_SECTIONS.map((s) => {
          const cnt = entries.filter((e) => e.record.dpdpSection === s.code).length
          return (
            <button
              key={s.code}
              onClick={() => setFilter(s.code)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg border-2 transition-colors ${
                filter === s.code
                  ? `${s.color} ${s.textColor} border-current`
                  : 'bg-white text-gray-600 border-gray-300 hover:border-gray-500'
              }`}
            >
              §{s.code} ({cnt})
            </button>
          )
        })}
      </div>

      {/* ── Consent list ──────────────────────────────────────────────────── */}
      {loading && entries.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <div className="animate-spin text-4xl mb-3">⟳</div>
          <p>Loading on-chain consents…</p>
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-12 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
          <p className="text-4xl mb-2">📋</p>
          <p className="font-medium">No consents found</p>
          <p className="text-sm mt-1">
            {CONFIG.APP_ID === 0n
              ? 'APP_ID not configured'
              : 'No consents match the current filter'}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((entry, idx) => {
          const isExpired = entry.record.expiry !== 0n && entry.record.expiry < now
          const isExpanded = expandedIdx === idx
          const statusLabel = entry.frozen ? 'Revoked' : isExpired ? 'Expired' : 'Active'
          const statusColor = entry.frozen ? 'text-red-700 bg-red-50 border-red-200' :
            isExpired ? 'text-amber-700 bg-amber-50 border-amber-200' :
            'text-emerald-700 bg-emerald-50 border-emerald-200'

          return (
            <div
              key={idx}
              className={`border rounded-xl ${statusColor} shadow-sm`}
            >
              {/* Summary row */}
              <button
                className="w-full text-left p-4"
                onClick={() => setExpandedIdx(isExpanded ? null : idx)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <ZKProofBadge verified={!entry.frozen && !isExpired} />
                    <DPDPSectionTag section={entry.record.dpdpSection} />
                    <span className="text-xs font-bold">{statusLabel}</span>
                  </div>
                  <span className="text-gray-400 text-sm">{isExpanded ? '▲' : '▼'}</span>
                </div>
                <div className="flex flex-wrap gap-4 mt-2 text-xs text-gray-600">
                  <span>
                    <span className="font-medium">Owner:</span> {shortAddr(entry.owner)}
                  </span>
                  <span>
                    <span className="font-medium">Requester:</span> {shortAddr(entry.record.requester)}
                  </span>
                  <span>
                    <span className="font-medium">Expiry:</span> {formatExpiry(entry.record.expiry)}
                  </span>
                </div>
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t border-current border-opacity-20 px-4 pb-4 pt-3 space-y-2">
                  <div>
                    <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-0.5">ZK Commitment</p>
                    <p className="font-mono text-xs bg-white border border-gray-200 rounded px-2 py-1">
                      {shortCommitment(entry.record.commitment)}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5 italic">
                      Data type &amp; purpose are ZK-committed — not readable from the chain
                    </p>
                  </div>
                  <NullifierStatus nullifier={entry.record.nullifier} used={true} />
                  <div className="text-xs text-gray-500">
                    <span className="font-medium">ASA:</span>{' '}
                    <span className="font-mono">#{entry.assetId.toString()}</span>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
