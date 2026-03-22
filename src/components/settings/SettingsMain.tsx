import { useEffect } from 'react'
import { useSettingsStore } from '../../store/settings'

const LOCALES = [
  { value: 'zh_CN', label: '中文（简体）' },
  { value: 'en_US', label: 'English (US)' },
  { value: 'fr_FR', label: 'Français' },
]

const RECORDING_MODES = [
  { value: 'record_only',              label: 'Record Only' },
  { value: 'transcribe_only',          label: 'Transcribe' },
  { value: 'transcribe_and_translate', label: 'Transcribe & Translate' },
]

const LLM_TASKS = [
  { value: 'summary',       label: 'Summary' },
  { value: 'meeting_brief', label: 'Meeting Brief' },
]

export function SettingsMain() {
  const { config, isLoading, error, loadConfig, updateConfig, resetConfig } =
    useSettingsStore()

  useEffect(() => {
    if (!config) loadConfig()
  }, [config, loadConfig])

  if (isLoading && !config) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted text-sm">
        Loading settings…
      </div>
    )
  }

  if (!config) return null

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-text-primary">General Settings</h1>
        <button
          onClick={() => resetConfig()}
          className="rounded border border-border px-3 py-1.5 text-sm text-text-secondary
                     hover:border-status-error hover:text-status-error transition-colors"
        >
          Reset to Defaults
        </button>
      </div>

      {error && (
        <p className="rounded bg-status-error/10 px-3 py-2 text-sm text-status-error">
          {error}
        </p>
      )}

      {/* ── Language & Display ── */}
      <section className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
          Language &amp; Display
        </h2>

        <FormRow label="Interface Language">
          <Select
            value={config.locale}
            options={LOCALES}
            onChange={(v) => updateConfig({ locale: v })}
          />
        </FormRow>
      </section>

      {/* ── Recording ── */}
      <section className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
          Recording
        </h2>

        <FormRow label="Default Recording Mode">
          <Select
            value={config.default_recording_mode}
            options={RECORDING_MODES}
            onChange={(v) => updateConfig({ default_recording_mode: v })}
          />
        </FormRow>

        <FormRow label="Default Language (transcription)">
          <input
            type="text"
            placeholder="auto"
            value={config.default_language ?? ''}
            onChange={(e) =>
              updateConfig({
                default_language: e.target.value === '' ? null : e.target.value,
              })
            }
            className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                       text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </FormRow>

        <FormRow label="VAD Threshold">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0.001}
                max={0.1}
                step={0.001}
                value={Math.min(config.vad_threshold, 0.1)}
                onChange={(e) =>
                  updateConfig({ vad_threshold: parseFloat(e.target.value) })
                }
                className="flex-1"
              />
              <span className="w-14 text-right text-sm text-text-secondary font-mono">
                {config.vad_threshold.toFixed(3)}
              </span>
            </div>
            <p className="text-xs text-text-muted">
              Lower = more sensitive. iPhone/external mics often need 0.005–0.020.
              Check terminal for actual RMS values.
            </p>
          </div>
        </FormRow>

        <FormRow label="Auto AI processing after stop">
          <input
            type="checkbox"
            checked={config.auto_llm_on_stop}
            onChange={(e) => updateConfig({ auto_llm_on_stop: e.target.checked })}
            className="h-4 w-4 rounded border-border accent-accent"
          />
        </FormRow>
      </section>

      {/* ── AI ── */}
      <section className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
          AI
        </h2>

        <FormRow label="Default AI Task">
          <Select
            value={config.default_llm_task}
            options={LLM_TASKS}
            onChange={(v) => updateConfig({ default_llm_task: v })}
          />
        </FormRow>

        <FormRow label="LLM Context Size (tokens)">
          <input
            type="number"
            min={512}
            max={32768}
            step={512}
            value={config.llm_context_size}
            onChange={(e) =>
              updateConfig({ llm_context_size: parseInt(e.target.value, 10) })
            }
            className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                       text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </FormRow>
      </section>

      {/* ── Models ── */}
      <section className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
          Models
        </h2>

        <FormRow label="Download Mirror">
          <Select
            value={config.model_mirror ?? ''}
            options={[
              { value: '',          label: 'Default (huggingface.co)' },
              { value: 'hf-mirror', label: 'hf-mirror.com (China)' },
            ]}
            onChange={(v) => updateConfig({ model_mirror: v })}
          />
        </FormRow>
        <p className="text-xs text-text-muted -mt-2 ml-56">
          Switch mirror if huggingface.co is inaccessible in your region.
        </p>
      </section>

      {/* ── Storage ── */}
      <section className="space-y-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-muted">
          Storage
        </h2>

        <FormRow label="Vault Path">
          <input
            type="text"
            value={config.vault_path}
            onChange={(e) => updateConfig({ vault_path: e.target.value })}
            className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                       text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </FormRow>

        <FormRow label="Recordings Path">
          <input
            type="text"
            value={config.recordings_path}
            onChange={(e) => updateConfig({ recordings_path: e.target.value })}
            className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                       text-sm text-text-primary focus:outline-none focus:border-accent"
          />
        </FormRow>
      </section>
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function FormRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-4">
      <label className="w-52 shrink-0 text-sm text-text-secondary">{label}</label>
      <div className="flex-1">{children}</div>
    </div>
  )
}

function Select({
  value,
  options,
  onChange,
}: {
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded border border-border bg-bg-input px-3 py-1.5
                 text-sm text-text-primary focus:outline-none focus:border-accent"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}
