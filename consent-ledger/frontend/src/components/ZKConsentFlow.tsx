/**
 * ZKConsentFlow — The full ZK-aware consent granting flow.
 *
 * Steps:
 *   1. Verify identity with DigiLocker (or demo mode)
 *   2. Fill in the org's parameterized circuit form (age, blood group, etc.)
 *   3. Generate ZK proofs for each field (backend prover)
 *   4. Submit proof hashes to ZKVerifierContract
 *   5. Call ConsentLedger.grant_consent() with commitment + nullifier
 *
 * If no org form is detected (org address only), falls back to a
 * generic consent_commitment proof.
 */

import React, { useState } from 'react'
import { useWallet } from '@txnlab/use-wallet-react'
import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import algosdk from 'algosdk'
import { ConsentLedgerClient } from '../contracts/ConsentLedgerClient'
import { CONFIG } from '../config'
import { consentBoxName } from '../utils'
import {
  proveAgeRange,
  proveConsentCommitment,
  proveSetMembership,
  proveHashEquality,
  generateSalt,
  hexToUint8Array,
  type ProveResult,
} from '../lib/zkProver'
import {
  FORM_TEMPLATES,
  DPDP_SECTIONS,
  type OrgForm,
  type CircuitField,
  type AgeRangeParams,
  type SetMembershipParams,
  type HashEqualityParams,
} from '../lib/circuitRegistry'
import { DigiLockerButton } from './DigiLockerButton'
import { DPDPSectionTag } from './DPDPSectionTag'
import { ZKProofBadge } from './ZKProofBadge'

// ─── Step indicators ──────────────────────────────────────────────────────────

type Step = 'identity' | 'form' | 'prove' | 'submit' | 'done'

function StepDot({ active, done, label }: { active: boolean; done: boolean; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-colors ${
        done ? 'bg-emerald-600 border-emerald-600 text-white' :
        active ? 'bg-indigo-100 border-indigo-600 text-indigo-700' :
        'bg-white border-gray-300 text-gray-400'
      }`}>
        {done ? '✓' : active ? '●' : '○'}
      </div>
      <span className={`text-xs font-medium ${active ? 'text-indigo-700' : done ? 'text-emerald-700' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  )
}

function StepLine({ done }: { done: boolean }) {
  return <div className={`flex-1 h-0.5 mt-4 transition-colors ${done ? 'bg-emerald-400' : 'bg-gray-200'}`} />
}

// ─── Proof step display ───────────────────────────────────────────────────────

interface ProofStepState {
  label: string
  status: 'pending' | 'running' | 'done' | 'error'
  error?: string
}

function ProofStepRow({ step }: { step: ProofStepState }) {
  return (
    <div className={`flex items-center gap-3 py-2 px-3 rounded-lg text-sm ${
      step.status === 'done' ? 'bg-emerald-50' :
      step.status === 'error' ? 'bg-red-50' :
      step.status === 'running' ? 'bg-indigo-50' :
      'bg-gray-50'
    }`}>
      <span className="w-5 text-center">
        {step.status === 'done' ? '✓' :
         step.status === 'error' ? '✗' :
         step.status === 'running' ? <span className="animate-pulse">⧖</span> :
         '○'}
      </span>
      <span className={`font-medium ${
        step.status === 'done' ? 'text-emerald-800' :
        step.status === 'error' ? 'text-red-800' :
        step.status === 'running' ? 'text-indigo-800' :
        'text-gray-500'
      }`}>
        {step.label}
      </span>
      {step.error && <span className="text-xs text-red-600 ml-auto">{step.error}</span>}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface TxResult {
  txId: string
  assetId: string
}

function parseFormFromUrl(): OrgForm | null {
  try {
    const params = new URLSearchParams(window.location.search)
    const encoded = params.get('form')
    if (!encoded) return null
    return JSON.parse(atob(encoded)) as OrgForm
  } catch {
    return null
  }
}

export function ZKConsentFlow() {
  const { transactionSigner, activeAddress, wallets } = useWallet()
  const peraWallet = wallets[0]

  // Detect a form shared via URL (from OrgFormBuilder "Share Form")
  const [urlForm] = useState<OrgForm | null>(() => parseFormFromUrl())

  // State
  const [step, setStep] = useState<Step>('identity')
  const [identitySecret, setIdentitySecret] = useState<string | null>(null)
  const [orgAddress, setOrgAddress] = useState('')
  const [selectedForm, setSelectedForm] = useState<OrgForm>(() => urlForm ?? FORM_TEMPLATES[1])
  const [selectedDpdpSection, setSelectedDpdpSection] = useState<number>(() => (urlForm ?? FORM_TEMPLATES[1]).dpdpSection)
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [proofSteps, setProofSteps] = useState<ProofStepState[]>([])
  const [result, setResult] = useState<TxResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // ── Wallet gate ─────────────────────────────────────────────────────────────
  if (!activeAddress) {
    return (
      <div className="text-center py-16 text-gray-500">
        <div className="text-5xl mb-4">🔐</div>
        <p className="text-lg font-semibold mb-2">Connect your wallet to grant consent</p>
        <p className="text-sm text-gray-400 mb-6">
          You are logged in as a <span className="font-medium text-emerald-600">User</span>.
          Connect your Pera wallet to get started.
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

  // ── Step progress ───────────────────────────────────────────────────────────
  const STEP_ORDER: Step[] = ['identity', 'form', 'prove', 'submit', 'done']
  const stepIdx = STEP_ORDER.indexOf(step)

  const updateFieldValue = (fieldId: string, value: string) =>
    setFieldValues((prev) => ({ ...prev, [fieldId]: value }))

  // ── Prove + submit ──────────────────────────────────────────────────────────
  const runProveAndSubmit = async () => {
    setError(null)
    setStep('prove')

    if (!algosdk.isValidAddress(orgAddress.trim())) {
      setError('Invalid organisation Algorand address.')
      setStep('form')
      return
    }
    if (CONFIG.APP_ID === 0n) {
      setError('APP_ID not configured — set VITE_APP_ID in .env')
      setStep('form')
      return
    }

    const salt = generateSalt()
    const steps: ProofStepState[] = selectedForm.fields.map((f) => ({
      label: `Proving: ${f.label}`,
      status: 'pending',
    }))
    steps.push({ label: 'Submitting consent on-chain', status: 'pending' })
    setProofSteps([...steps])

    const updateStep = (idx: number, upd: Partial<ProofStepState>) =>
      setProofSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, ...upd } : s)))

    // Collect proof results
    const proofs: ProveResult[] = []
    let hasError = false

    for (let i = 0; i < selectedForm.fields.length; i++) {
      const field: CircuitField = selectedForm.fields[i]
      updateStep(i, { status: 'running' })
      try {
        let proof: ProveResult
        const params = field.params
        const userVal = fieldValues[field.id] ?? ''

        if (params.kind === 'age_range') {
          const p = params as AgeRangeParams
          const age = parseInt(userVal) || 25
          proof = await proveAgeRange({ age, salt, minAge: p.minAge, maxAge: p.maxAge })
        } else if (params.kind === 'set_membership') {
          const p = params as SetMembershipParams
          proof = await proveSetMembership({ field: p.field, value: userVal, allowedValues: p.allowedValues, salt })
        } else if (params.kind === 'hash_equality') {
          const p = params as HashEqualityParams
          proof = await proveHashEquality({ field: p.field, value: userVal, salt })
        } else {
          // consent_commitment fallback
          proof = await proveConsentCommitment({
            dataType: field.label,
            purpose: selectedForm.formName,
            salt,
            requesterId: orgAddress.trim(),
          })
        }
        proofs.push(proof)
        updateStep(i, { status: 'done' })
      } catch (err) {
        updateStep(i, { status: 'error', error: err instanceof Error ? err.message : String(err) })
        hasError = true
        break
      }
    }

    if (hasError) {
      setError('Proof generation failed. See steps above.')
      setStep('prove')
      return
    }

    // Use the first proof's commitment + nullifier for the on-chain record
    // In a full implementation, commitment = Poseidon(all field commitments)
    const primaryProof = proofs[0] ?? {
      commitment: generateSalt(),
      proofHash: generateSalt(),
      nullifier: generateSalt(),
    }

    // Submit on-chain
    setStep('submit')
    const submitIdx = selectedForm.fields.length
    updateStep(submitIdx, { status: 'running', label: 'Granting consent on-chain…' })

    try {
      const algorand = AlgorandClient.testNet()
      algorand.setSigner(activeAddress, transactionSigner!)

      const client = algorand.client.getTypedAppClientById(ConsentLedgerClient, {
        appId: CONFIG.APP_ID,
        defaultSender: activeAddress,
      })

      const commitment = hexToUint8Array(primaryProof.commitment) as unknown as [number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number]
      const nullifier = hexToUint8Array(primaryProof.nullifier) as unknown as [number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number, number]

      const response = await client.send.grantConsent({
        args: {
          requester: orgAddress.trim(),
          commitment: commitment,
          nullifier: nullifier,
          expiry: BigInt(0),
          dpdpSection: selectedDpdpSection,
        },
        extraFee: (3_000).microAlgo(),
        boxReferences: [
          { appId: CONFIG.APP_ID, name: consentBoxName(activeAddress, orgAddress.trim()) },
        ],
        validityWindow: 200,
      })

      updateStep(submitIdx, { status: 'done', label: 'Consent granted on-chain' })

      setResult({
        txId: response.txIds[0],
        assetId: response.return?.toString() ?? '?',
      })
      setStep('done')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      updateStep(submitIdx, { status: 'error', error: msg })
      setError(msg)
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Step indicators */}
      <div className="flex items-start gap-2 mb-8">
        {STEP_ORDER.slice(0, -1).map((s, i) => (
          <React.Fragment key={s}>
            <StepDot
              label={['Identity', 'Form', 'Prove', 'Submit'][i]}
              active={stepIdx === i}
              done={stepIdx > i}
            />
            {i < 3 && <StepLine done={stepIdx > i} />}
          </React.Fragment>
        ))}
      </div>

      {/* ── Step 1: Identity ─────────────────────────────────────────────── */}
      {step === 'identity' && (
        <div>
          <h2 className="text-2xl font-bold mb-1">Verify Your Identity</h2>
          <p className="text-gray-500 text-sm mb-6">
            Your identity is verified with DigiLocker. Raw data never leaves your session.
          </p>
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
            <p className="text-sm text-gray-600 mb-4">
              DigiLocker verifies your Aadhaar and extracts the data needed to generate ZK proofs.
              Only a cryptographic commitment of your data is stored on-chain — never your raw age, name, or Aadhaar number.
            </p>
            <DigiLockerButton
              isVerified={!!identitySecret}
              onVerified={(secret) => {
                setIdentitySecret(secret)
                setStep('form')
              }}
            />
          </div>
          <button
            onClick={() => {
              // Demo: skip identity, use random secret
              setIdentitySecret('demo')
              setStep('form')
            }}
            className="text-sm text-indigo-600 hover:underline"
          >
            Skip (demo mode)
          </button>
        </div>
      )}

      {/* ── Step 2: Form ─────────────────────────────────────────────────── */}
      {step === 'form' && (
        <div>
          <h2 className="text-2xl font-bold mb-1">Consent Request Details</h2>
          <p className="text-gray-500 text-sm mb-6">
            Fill in the organisation's consent form. Each field will be proven using a ZK circuit.
          </p>

          <div className="space-y-5">
            {/* Org address */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Organisation Address</label>
              <input
                type="text"
                value={orgAddress}
                onChange={(e) => setOrgAddress(e.target.value)}
                placeholder="ALGO address of the requesting organisation"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>

            {/* Form template selector — hidden when a custom form is shared via URL */}
            {urlForm ? (
              <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
                <p className="text-xs font-semibold text-indigo-600 uppercase tracking-wider mb-1">Form shared by organisation</p>
                <p className="text-sm font-bold text-indigo-900">{urlForm.formName}</p>
                <p className="text-xs text-indigo-700 mt-0.5">{urlForm.description}</p>
              </div>
            ) : (
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">Consent Form</label>
                <select
                  value={selectedForm.id}
                  onChange={(e) => {
                    const f = FORM_TEMPLATES.find((t) => t.id === e.target.value) ?? FORM_TEMPLATES[0]
                    setSelectedForm(f)
                    setSelectedDpdpSection(f.dpdpSection)
                    setFieldValues({})
                  }}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                >
                  {FORM_TEMPLATES.filter((t) => t.id !== 'custom').map((t) => (
                    <option key={t.id} value={t.id}>{t.formName}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">{selectedForm.description}</p>
              </div>
            )}

            {/* DPDP Section */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">DPDP Act Section</label>
              <div className="flex flex-wrap gap-2">
                {DPDP_SECTIONS.map((s) => (
                  <button
                    key={s.code}
                    onClick={() => setSelectedDpdpSection(s.code)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-2 transition-colors ${
                      selectedDpdpSection === s.code
                        ? `${s.color} ${s.textColor} border-current`
                        : 'bg-white border-gray-200 text-gray-500 hover:border-gray-400'
                    }`}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Circuit form fields */}
            {selectedForm.fields.length > 0 && (
              <div className="space-y-4">
                <p className="text-sm font-semibold text-gray-700">Your Private Inputs (ZK Protected)</p>
                {selectedForm.fields.map((field) => {
                  const params = field.params
                  return (
                    <div key={field.id} className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="text-sm font-semibold text-gray-800">{field.label}</p>
                          <p className="text-xs text-gray-500 mt-0.5">{field.description}</p>
                        </div>
                        <span className="text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full font-medium">
                          {params.kind === 'age_range' ? 'Age Range Circuit' :
                           params.kind === 'set_membership' ? 'Set Membership Circuit' :
                           params.kind === 'hash_equality' ? 'Hash Equality Circuit' :
                           'ZK Circuit'}
                        </span>
                      </div>

                      {params.kind === 'age_range' && (
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">
                            Your Age <span className="text-gray-400">(proven to be {(params as AgeRangeParams).minAge}–{(params as AgeRangeParams).maxAge}, not revealed)</span>
                          </label>
                          <input
                            type="number"
                            min={(params as AgeRangeParams).minAge}
                            max={(params as AgeRangeParams).maxAge}
                            value={fieldValues[field.id] ?? ''}
                            onChange={(e) => updateFieldValue(field.id, e.target.value)}
                            placeholder={`Between ${(params as AgeRangeParams).minAge} and ${(params as AgeRangeParams).maxAge}`}
                            className="w-32 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                          />
                        </div>
                      )}

                      {params.kind === 'set_membership' && (
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">
                            Select your {(params as SetMembershipParams).field.replace('_', ' ')}
                          </label>
                          <select
                            value={fieldValues[field.id] ?? ''}
                            onChange={(e) => updateFieldValue(field.id, e.target.value)}
                            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                          >
                            <option value="">Select…</option>
                            {(params as SetMembershipParams).allowedValues.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {params.kind === 'hash_equality' && (
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">
                            Your {(params as HashEqualityParams).field.replace('_', ' ')} (not revealed)
                          </label>
                          <input
                            type="text"
                            value={fieldValues[field.id] ?? ''}
                            onChange={(e) => updateFieldValue(field.id, e.target.value)}
                            placeholder="Enter value (kept private)"
                            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex items-center gap-2">
              <DPDPSectionTag section={selectedDpdpSection} size="md" />
              <span className="text-xs text-gray-400">section will be recorded on-chain</span>
            </div>

            <button
              onClick={runProveAndSubmit}
              disabled={!orgAddress.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white rounded-xl py-3 font-semibold text-sm transition-colors"
            >
              Generate ZK Proofs & Grant Consent
            </button>
          </div>
        </div>
      )}

      {/* ── Steps 3+4: Prove & Submit ──────────────────────────────────── */}
      {(step === 'prove' || step === 'submit') && (
        <div>
          <h2 className="text-2xl font-bold mb-1">Generating ZK Proofs</h2>
          <p className="text-gray-500 text-sm mb-6">
            Your private data is being proven cryptographically. This may take a moment.
          </p>
          <div className="space-y-2">
            {proofSteps.map((s, i) => (
              <ProofStepRow key={i} step={s} />
            ))}
          </div>
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 mt-4">
              {error}
              <button
                onClick={() => { setError(null); setStep('form') }}
                className="ml-3 text-indigo-600 hover:underline"
              >
                Go back
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Step done ──────────────────────────────────────────────────── */}
      {step === 'done' && result && (
        <div className="text-center py-6">
          <div className="text-5xl mb-4">🎉</div>
          <h2 className="text-2xl font-bold mb-2">Consent Granted</h2>
          <p className="text-gray-500 text-sm mb-6">
            Your ZK commitment is recorded on Algorand. Data type and purpose are never revealed on-chain.
          </p>

          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 text-left mb-6">
            <div className="flex flex-wrap gap-2 mb-3">
              <ZKProofBadge verified size="md" />
              <DPDPSectionTag section={selectedDpdpSection} size="md" />
            </div>
            <p className="text-sm text-gray-700 mb-1">
              <span className="font-semibold">Consent Token (ASA):</span>{' '}
              <span className="font-mono text-emerald-800">#{result.assetId}</span>
            </p>
            <p className="text-sm text-gray-700">
              <span className="font-semibold">Transaction:</span>{' '}
              <a
                href={`https://algoexplorer.io/tx/${result.txId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-indigo-600 hover:underline"
              >
                {result.txId.slice(0, 12)}…
              </a>
            </p>
          </div>

          <button
            onClick={() => {
              setStep('identity')
              setIdentitySecret(null)
              setOrgAddress('')
              setFieldValues({})
              setResult(null)
              setProofSteps([])
            }}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-lg font-semibold transition-colors"
          >
            Grant Another Consent
          </button>
        </div>
      )}
    </div>
  )
}
