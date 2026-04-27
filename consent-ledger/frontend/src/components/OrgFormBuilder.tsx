/**
 * OrgFormBuilder — lets an organisation define a parameterized circuit consent form.
 *
 * The org picks from the circuit library, sets parameters (e.g., age min/max,
 * allowed blood groups), and gets a shareable URL or QR code with the form schema.
 *
 * This is the Phase 4 implementation of the ZK_REGISTRY_FOR_ORGANIZATIONS concept:
 *   "forms will be different for different use-cases"
 *   "ZK circuits designed on very specific questions (is blood group compatible...)"
 *
 * Form schemas are composed from the CIRCUIT_LIBRARY of pre-audited, parameterized
 * circuits — no new circuits are compiled at runtime (as per the architectural decision).
 */

import { useState } from 'react'
import {
  CIRCUIT_LIBRARY,
  FORM_TEMPLATES,
  DPDP_SECTIONS,
  type OrgForm,
  type CircuitField,
  type AgeRangeParams,
  type SetMembershipParams,
  type HashEqualityParams,
  type CircuitDef,
} from '../lib/circuitRegistry'
import { DPDPSectionTag } from './DPDPSectionTag'

// ─── Field editor ─────────────────────────────────────────────────────────────

interface FieldEditorProps {
  field: CircuitField
  onChange: (updated: CircuitField) => void
  onRemove: () => void
}

function FieldEditor({ field, onChange, onRemove }: FieldEditorProps) {
  const update = (partial: Partial<CircuitField>) => onChange({ ...field, ...partial })
  const params = field.params

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <input
            type="text"
            value={field.label}
            onChange={(e) => update({ label: e.target.value })}
            className="w-full text-sm font-semibold border-b border-gray-200 focus:outline-none focus:border-indigo-400 pb-0.5 mb-1"
            placeholder="Field label (shown to user)"
          />
          <input
            type="text"
            value={field.description}
            onChange={(e) => update({ description: e.target.value })}
            className="w-full text-xs text-gray-500 border-b border-gray-100 focus:outline-none focus:border-indigo-300 pb-0.5"
            placeholder="Description / helper text"
          />
        </div>
        <button onClick={onRemove} className="ml-3 text-red-400 hover:text-red-600 text-lg leading-none">×</button>
      </div>

      {/* Circuit type badge */}
      <div className="mb-3">
        <span className="text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full">
          {CIRCUIT_LIBRARY.find((c) => c.code === field.circuitType)?.name ?? 'Unknown Circuit'}
        </span>
      </div>

      {/* Age range params */}
      {params.kind === 'age_range' && (
        <div className="flex items-center gap-3">
          <label className="text-xs text-gray-600">Min age:</label>
          <input
            type="number"
            value={(params as AgeRangeParams).minAge}
            onChange={(e) => onChange({ ...field, params: { ...(params as AgeRangeParams), minAge: parseInt(e.target.value) || 0 } })}
            className="w-16 border border-gray-300 rounded px-2 py-1 text-sm"
          />
          <label className="text-xs text-gray-600">Max age:</label>
          <input
            type="number"
            value={(params as AgeRangeParams).maxAge}
            onChange={(e) => onChange({ ...field, params: { ...(params as AgeRangeParams), maxAge: parseInt(e.target.value) || 0 } })}
            className="w-16 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </div>
      )}

      {/* Set membership params */}
      {params.kind === 'set_membership' && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <label className="text-xs text-gray-600 w-16">Field name:</label>
            <input
              type="text"
              value={(params as SetMembershipParams).field}
              onChange={(e) => onChange({ ...field, params: { ...(params as SetMembershipParams), field: e.target.value } })}
              className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
              placeholder="e.g. blood_group"
            />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">
              Allowed values <span className="text-gray-400">(comma-separated)</span>:
            </label>
            <input
              type="text"
              value={(params as SetMembershipParams).allowedValues.join(', ')}
              onChange={(e) =>
                onChange({
                  ...field,
                  params: {
                    ...(params as SetMembershipParams),
                    allowedValues: e.target.value.split(',').map((v) => v.trim()).filter(Boolean),
                  },
                })
              }
              className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
              placeholder="e.g. B+, AB+, O+"
            />
          </div>
        </div>
      )}

      {/* Hash equality params */}
      {params.kind === 'hash_equality' && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-600 w-16">Field:</label>
          <input
            type="text"
            value={(params as HashEqualityParams).field}
            onChange={(e) => onChange({ ...field, params: { ...(params as HashEqualityParams), field: e.target.value } })}
            className="flex-1 border border-gray-300 rounded px-2 py-1 text-xs"
            placeholder="e.g. aadhaar_number"
          />
        </div>
      )}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function OrgFormBuilder() {
  const [form, setForm] = useState<OrgForm>(() => ({
    id: 'custom_' + Date.now(),
    formName: 'My Consent Form',
    description: 'Describe what this form is for',
    dpdpSection: 6,
    fields: [],
  }))
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [previewMode, setPreviewMode] = useState(false)
  const [addingCircuit, setAddingCircuit] = useState(false)

  const updateField = (idx: number, updated: CircuitField) =>
    setForm((f) => ({ ...f, fields: f.fields.map((field, i) => (i === idx ? updated : field)) }))

  const removeField = (idx: number) =>
    setForm((f) => ({ ...f, fields: f.fields.filter((_, i) => i !== idx) }))

  const addField = (def: CircuitDef) => {
    const newField: CircuitField = {
      id: def.name.toLowerCase().replace(/\s+/g, '_') + '_' + Date.now(),
      label: def.name,
      description: def.description,
      circuitType: def.code,
      userInputType: def.inputType,
      params: { ...def.defaultParams },
    }
    setForm((f) => ({ ...f, fields: [...f.fields, newField] }))
    setAddingCircuit(false)
  }

  const loadTemplate = (templateId: string) => {
    const t = FORM_TEMPLATES.find((f) => f.id === templateId)
    if (t) setForm({ ...t, id: 'custom_' + Date.now() })
  }

  const generateShareUrl = () => {
    const encoded = btoa(JSON.stringify(form))
    const url = `${window.location.origin}?form=${encoded}`
    setShareUrl(url)
    navigator.clipboard.writeText(url).catch(() => {})
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Consent Form Builder</h2>
          <p className="text-gray-500 text-sm">
            Design parameterized ZK circuit forms. Users prove data without revealing it.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setPreviewMode((p) => !p)}
            className="px-3 py-1.5 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {previewMode ? 'Edit' : 'Preview'}
          </button>
          <button
            onClick={generateShareUrl}
            className="px-3 py-1.5 text-sm font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors"
          >
            Share Form
          </button>
        </div>
      </div>

      {shareUrl && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-5 text-sm">
          <p className="font-semibold text-emerald-800 mb-1">Form URL copied to clipboard!</p>
          <p className="font-mono text-xs text-emerald-700 break-all">{shareUrl}</p>
          <p className="text-xs text-emerald-600 mt-1">
            Share this URL with your users. They will see this form when granting consent to your organisation.
          </p>
        </div>
      )}

      {!previewMode ? (
        /* ── Edit mode ─────────────────────────────────────────────── */
        <div className="space-y-5">
          {/* Form metadata */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1">Form Name</label>
              <input
                type="text"
                value={form.formName}
                onChange={(e) => setForm((f) => ({ ...f, formName: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1">Description</label>
              <input
                type="text"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">DPDP Act Section</label>
              <div className="flex flex-wrap gap-2">
                {DPDP_SECTIONS.map((s) => (
                  <button
                    key={s.code}
                    onClick={() => setForm((f) => ({ ...f, dpdpSection: s.code }))}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border-2 transition-colors ${
                      form.dpdpSection === s.code
                        ? `${s.color} ${s.textColor} border-current`
                        : 'bg-white border-gray-200 text-gray-500 hover:border-gray-400'
                    }`}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Load template */}
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-500">Load template:</span>
            {FORM_TEMPLATES.filter((t) => t.id !== 'custom').map((t) => (
              <button
                key={t.id}
                onClick={() => loadTemplate(t.id)}
                className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs font-medium text-gray-700 transition-colors"
              >
                {t.formName}
              </button>
            ))}
          </div>

          {/* Fields */}
          <div className="space-y-3">
            {form.fields.length === 0 && (
              <div className="text-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
                <p className="text-4xl mb-2">⚙️</p>
                <p className="font-medium">No circuit fields yet</p>
                <p className="text-sm mt-1">Add a circuit from the library below</p>
              </div>
            )}
            {form.fields.map((field, idx) => (
              <FieldEditor
                key={field.id}
                field={field}
                onChange={(updated) => updateField(idx, updated)}
                onRemove={() => removeField(idx)}
              />
            ))}
          </div>

          {/* Add circuit */}
          {addingCircuit ? (
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-indigo-800 mb-3">Pick a circuit from the library:</p>
              <div className="grid grid-cols-1 gap-2">
                {CIRCUIT_LIBRARY.map((def) => (
                  <button
                    key={def.code}
                    onClick={() => addField(def)}
                    className="flex items-start gap-3 text-left px-4 py-3 bg-white hover:bg-indigo-50 border border-indigo-100 rounded-lg transition-colors"
                  >
                    <div>
                      <p className="text-sm font-semibold text-gray-800">{def.name}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{def.description}</p>
                    </div>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setAddingCircuit(false)}
                className="mt-3 text-xs text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAddingCircuit(true)}
              className="w-full py-2.5 border-2 border-dashed border-indigo-300 hover:border-indigo-500 hover:bg-indigo-50 rounded-xl text-sm font-semibold text-indigo-600 transition-colors"
            >
              + Add Circuit Field
            </button>
          )}
        </div>
      ) : (
        /* ── Preview mode ──────────────────────────────────────────── */
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-6">
          <p className="text-xs text-gray-400 uppercase tracking-wider font-medium mb-4">User Preview</p>
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xl font-bold">{form.formName}</h3>
            <DPDPSectionTag section={form.dpdpSection} />
          </div>
          <p className="text-sm text-gray-500 mb-5">{form.description}</p>
          {form.fields.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No fields defined.</p>
          ) : (
            <div className="space-y-3">
              {form.fields.map((field) => {
                const params = field.params
                return (
                  <div key={field.id} className="bg-white border border-gray-200 rounded-xl p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="text-sm font-semibold text-gray-800">{field.label}</p>
                        <p className="text-xs text-gray-500">{field.description}</p>
                      </div>
                      <span className="text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded-full">
                        {CIRCUIT_LIBRARY.find((c) => c.code === field.circuitType)?.name ?? 'ZK Circuit'}
                      </span>
                    </div>
                    {params.kind === 'age_range' && (
                      <p className="text-xs text-gray-400">
                        Accepted range: {(params as AgeRangeParams).minAge}–{(params as AgeRangeParams).maxAge} years
                      </p>
                    )}
                    {params.kind === 'set_membership' && (
                      <p className="text-xs text-gray-400">
                        Accepted values: {(params as SetMembershipParams).allowedValues.join(', ')}
                      </p>
                    )}
                    {params.kind === 'hash_equality' && (
                      <p className="text-xs text-gray-400">
                        Proves knowledge of: {(params as HashEqualityParams).field}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
