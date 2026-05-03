/**
 * Circuit Registry — parameterized ZK circuit definitions.
 *
 * Each entry defines a circuit type that an organisation can embed in a form.
 * Users fill in private values; the backend prover generates the ZK proof.
 * No raw values touch the chain — only commitments / proof hashes.
 *
 * Matches the Go circuits in consent-ledger/circuits/:
 *   0 = age_range          (age_range.go)
 *   1 = consent_commitment (consent_commitment.go)
 *   2 = nullifier          (nullifier.go)
 *   3 = set_membership     (future: Phase 4 extension)
 *   4 = hash_equality      (future: Phase 4 extension)
 *
 * An OrgForm is a list of CircuitField entries.
 * When a user fills the form, each field generates one proof.
 * The combined commitment stored on-chain is Poseidon over all field commitments.
 */

// ─── Circuit type codes ──────────────────────────────────────────────────────

export type CircuitTypeCode = 0 | 1 | 2 | 3 | 4

export const CIRCUIT_TYPE_CODE = {
  age_range:           0 as CircuitTypeCode,
  consent_commitment:  1 as CircuitTypeCode,
  nullifier:           2 as CircuitTypeCode,
  set_membership:      3 as CircuitTypeCode,
  hash_equality:       4 as CircuitTypeCode,
} as const

// ─── Field definitions ───────────────────────────────────────────────────────

export type UserInputType = 'number' | 'select' | 'text' | 'date'

/** A single field in an org's question form */
export interface CircuitField {
  id: string                     // unique key within the form
  label: string                  // shown to the user
  description: string            // helper text
  circuitType: CircuitTypeCode
  userInputType: UserInputType

  // type-specific constraints shown in the UI
  params: AgeRangeParams | SetMembershipParams | HashEqualityParams | NullifierParams
}

export interface AgeRangeParams {
  kind: 'age_range'
  minAge: number
  maxAge: number
}

export interface SetMembershipParams {
  kind: 'set_membership'
  field: string              // logical field name (e.g. "blood_group")
  allowedValues: string[]
}

export interface HashEqualityParams {
  kind: 'hash_equality'
  field: string              // logical field name (e.g. "aadhaar_number")
}

export interface NullifierParams {
  kind: 'nullifier'
}

// ─── Pre-built form templates ────────────────────────────────────────────────

export interface OrgForm {
  id: string
  formName: string
  description: string
  dpdpSection: 6 | 9 | 11 | 16
  fields: CircuitField[]
}

/** Pre-built form templates an org can pick from */
export const FORM_TEMPLATES: OrgForm[] = [
  // ── Health Screening ──────────────────────────────────────────────────────
  {
    id: 'health_screening',
    formName: 'Health Screening',
    description: 'Age and blood-group verification for clinical research',
    dpdpSection: 6,
    fields: [
      {
        id: 'age',
        label: 'Age Verification',
        description: 'Proves you are between 18 and 65 without revealing your exact age',
        circuitType: CIRCUIT_TYPE_CODE.age_range,
        userInputType: 'number',
        params: { kind: 'age_range', minAge: 18, maxAge: 65 },
      },
      {
        id: 'blood_group',
        label: 'Blood Group',
        description: 'Proves your blood group is in the accepted set (B+, AB+, O+)',
        circuitType: CIRCUIT_TYPE_CODE.set_membership,
        userInputType: 'select',
        params: { kind: 'set_membership', field: 'blood_group', allowedValues: ['B+', 'AB+', 'O+'] },
      },
    ],
  },

  // ── Standard KYC ─────────────────────────────────────────────────────────
  {
    id: 'standard_kyc',
    formName: 'Standard KYC',
    description: 'Age-gated identity check for financial services (§6)',
    dpdpSection: 6,
    fields: [
      {
        id: 'age_adult',
        label: 'Adult Verification (18+)',
        description: 'Proves you are at least 18 years old',
        circuitType: CIRCUIT_TYPE_CODE.age_range,
        userInputType: 'number',
        params: { kind: 'age_range', minAge: 18, maxAge: 120 },
      },
      {
        id: 'aadhaar',
        label: 'Aadhaar Identity Commitment',
        description: 'Proves you hold a valid Aadhaar number without revealing it',
        circuitType: CIRCUIT_TYPE_CODE.hash_equality,
        userInputType: 'text',
        params: { kind: 'hash_equality', field: 'aadhaar_number' },
      },
    ],
  },

  // ── Children's Data (§9) ──────────────────────────────────────────────────
  {
    id: 'children_guardian',
    formName: "Guardian Verification (§9 Children's Data)",
    description: 'Proves the consenting adult is a guardian aged 18+ (DPDP Act §9)',
    dpdpSection: 9,
    fields: [
      {
        id: 'guardian_age',
        label: 'Guardian Age (18+)',
        description: 'Proves the guardian is at least 18 years old',
        circuitType: CIRCUIT_TYPE_CODE.age_range,
        userInputType: 'number',
        params: { kind: 'age_range', minAge: 18, maxAge: 120 },
      },
    ],
  },

  // ── Custom (blank) ────────────────────────────────────────────────────────
  {
    id: 'custom',
    formName: 'Custom Form',
    description: 'Build your own consent form from the circuit library',
    dpdpSection: 6,
    fields: [],
  },
]

// ─── Available circuit definitions (for the form builder UI) ─────────────────

export interface CircuitDef {
  code: CircuitTypeCode
  name: string
  description: string
  inputType: UserInputType
  defaultParams: AgeRangeParams | SetMembershipParams | HashEqualityParams | NullifierParams
}

export const CIRCUIT_LIBRARY: CircuitDef[] = [
  {
    code: CIRCUIT_TYPE_CODE.age_range,
    name: 'Age Range',
    description: 'Proves min_age ≤ age ≤ max_age without revealing the actual age',
    inputType: 'number',
    defaultParams: { kind: 'age_range', minAge: 18, maxAge: 120 },
  },
  {
    code: CIRCUIT_TYPE_CODE.set_membership,
    name: 'Set Membership',
    description: 'Proves value ∈ allowed_set (e.g., blood group, nationality)',
    inputType: 'select',
    defaultParams: { kind: 'set_membership', field: 'value', allowedValues: [] },
  },
  {
    code: CIRCUIT_TYPE_CODE.hash_equality,
    name: 'Identity Commitment',
    description: 'Proves knowledge of a secret field (e.g., Aadhaar) without revealing it',
    inputType: 'text',
    defaultParams: { kind: 'hash_equality', field: 'secret_field' },
  },
  {
    code: CIRCUIT_TYPE_CODE.consent_commitment,
    name: 'Consent Commitment',
    description: 'Proves knowledge of data_type + purpose that hash to the on-chain commitment',
    inputType: 'text',
    defaultParams: { kind: 'hash_equality', field: 'consent_data' },
  },
]

// ─── DPDP Section metadata ────────────────────────────────────────────────────

export interface DPDPSectionMeta {
  code: 6 | 9 | 11 | 16
  name: string
  description: string
  color: string   // Tailwind bg class
  textColor: string
}

export const DPDP_SECTIONS: DPDPSectionMeta[] = [
  { code: 6,  name: '§6 Standard Consent',     description: 'General personal data processing consent',         color: 'bg-blue-100',   textColor: 'text-blue-800'   },
  { code: 9,  name: "§9 Children's Data",       description: 'Guardian consent for processing minor\'s data',    color: 'bg-yellow-100', textColor: 'text-yellow-800' },
  { code: 11, name: '§11 Grievance',            description: 'Consent related to grievance redressal process',   color: 'bg-orange-100', textColor: 'text-orange-800' },
  { code: 16, name: '§16 DPB Audit',            description: 'Data Protection Board regulatory audit trail',     color: 'bg-purple-100', textColor: 'text-purple-800' },
]

export function getDPDPSection(code: number): DPDPSectionMeta {
  return DPDP_SECTIONS.find((s) => s.code === code) ?? DPDP_SECTIONS[0]
}
