# Settings Persistence + Latency Reduction Design

**Date**: 2026-03-21
**Status**: Approved
**Scope**: `src-tauri/src/config/schema.rs`, `src-tauri/src/commands/transcription.rs`, `src-tauri/src/transcription/pipeline.rs`, `src-tauri/src/audio/vad.rs`, `src/components/recording/RecordingPanel.tsx`, `src/components/recording/RecordingMain.tsx`, `src/routes/recording.tsx`, `src/store/recording.ts`, `src/store/settings.ts`, `src/components/layout/__tests__/integration.test.tsx`

---

## Problem

1. **Settings not persisted**: `RecordingPanel` only reads 3 of 6 user settings from `AppConfig` on mount, and never saves changes back. Users must re-select microphone, language, and mode on every app launch.

2. **Transcription latency too high**: End-to-end latency from speech pause to visible text is ~1.5–1.8s due to an over-conservative 800ms pause trigger, a 50ms polling loop, slow VAD cold-start calibration (5s), and 300ms frontend polling.

3. **Dead code**: `AppConfig.audio_chunk_ms` and `RealtimeConfig.chunk_duration_ms` are never consumed — the resampler always outputs fixed 100ms chunks (`OUTPUT_CHUNK = 1600` @ 16kHz). These fields mislead readers and expose unused API surface.

---

## Goals

- All 6 `RecordingPanel` settings (microphone, language, mode, target language, VAD threshold, auto-process) restore correctly on every app launch
- Microphone restores to the last-used device when available; falls back to system default otherwise
- Steady-state transcription latency reduced from ~1.8s to ~1.2s
- First-segment visible delay reduced from ~7s to ~4s (VAD cold-start calibration halved)
- Dead `audio_chunk_ms` / `chunk_duration_ms` fields removed from API and config

---

## Architecture

No new files. No DB schema changes. No new Tauri commands.

### Data Flow (Settings Persistence)

```
App launch
  → RecordingPanel mounts
  → getConfig() + loadDevices() called in parallel
  → setVadThreshold, setLanguage, setMode, setTargetLang, setAutoProcess, setSavedDeviceId
  → hasMountedRef.current = true
  → devices available: restore savedDeviceId → prefer last-used device, fall back to default
  → User changes setting → useEffect → updateConfig(partial) → persisted to DB
```

### Latency Reduction (Parameter Changes Only)

```
Speech ends
  → VadFilter: 500ms silence (was 800ms) + loop checks every 10ms (was 50ms)
  → run_inference spawned
  → Whisper inference: 300–600ms (unchanged)
  → result written to segments_cache
  → Frontend polls every 200ms (was 300ms)
  → Text visible
```

---

## Feature 1: Settings Persistence

### 1.1 Backend — `src-tauri/src/config/schema.rs`

**Add** `last_used_device_id: Option<String>` (default `None`):

```rust
// In AppConfig:
/// Last microphone device ID used. None = not yet set. Default: None
pub last_used_device_id: Option<String>,

// In AppConfig::default():
last_used_device_id: None,

// In PartialAppConfig:
#[serde(skip_serializing_if = "Option::is_none")]
pub last_used_device_id: Option<String>,

// In apply_partial:
if let Some(v) = partial.last_used_device_id { config.last_used_device_id = v; }
```

**Remove** `audio_chunk_ms` from `AppConfig`, `PartialAppConfig`, `apply_partial`, and `AppConfig::default()`. Update the schema test that references this field.

### 1.2 Backend — `src-tauri/src/commands/transcription.rs`

**Remove** `chunk_duration_ms: u32` from `RealtimeConfig`. It has never been read inside `start_realtime` (resampler uses a fixed `OUTPUT_CHUNK = 1600`).

### 1.3 Frontend — `src/components/recording/RecordingPanel.tsx`

**Mount effect** — read all 6 settings from AppConfig:

```tsx
const hasMountedRef = useRef(false)
const [savedDeviceId, setSavedDeviceId] = useState<string | null>(null)

useEffect(() => {
  commands.getConfig().then((r) => {
    if (r.status === 'ok' && r.data) {
      const cfg = r.data
      if (cfg.vad_threshold != null) setVadThreshold(Math.min(cfg.vad_threshold, 0.015))
      if (cfg.default_language)      setLanguage(cfg.default_language)
      if (cfg.default_recording_mode) setMode(cfg.default_recording_mode as typeof mode)
      if (cfg.default_target_language) setTargetLang(cfg.default_target_language)
      if (cfg.auto_llm_on_stop != null) setAutoProcess(cfg.auto_llm_on_stop)
      setSavedDeviceId(cfg.last_used_device_id ?? null)
      hasMountedRef.current = true
    }
  })
  loadDevices()
}, [loadDevices])
```

**Device restoration** — handles race between config load and device enumeration:

```tsx
// Replace existing device effect with:
useEffect(() => {
  if (!devices.length) return
  const preferred = savedDeviceId ? devices.find(d => d.id === savedDeviceId) : null
  const target = preferred ?? devices.find(d => d.is_default)
  if (target) setDeviceId(target.id)
}, [devices, savedDeviceId])
```

- `savedDeviceId` is state (not a ref), so the effect re-runs if config arrives after devices
- If the last-used device is no longer available (unplugged, Continuity Camera disconnected), falls back to system default automatically

**Save-back effects** — persist changes to AppConfig:

```tsx
// All logical settings — fires when any of these 5 values change
useEffect(() => {
  if (!hasMountedRef.current) return
  commands.updateConfig({
    default_language: language === 'auto' ? null : language,
    default_recording_mode: mode,
    default_target_language: targetLang,
    vad_threshold: vadThreshold,
    auto_llm_on_stop: autoProcess,
  })
}, [language, mode, targetLang, vadThreshold, autoProcess])

// Device ID — separate effect to avoid unnecessary writes when device list is loading
useEffect(() => {
  if (!hasMountedRef.current || !deviceId) return
  commands.updateConfig({ last_used_device_id: deviceId })
}, [deviceId])
```

- `hasMountedRef.current` is `false` on the initial render with default values, preventing the first effect from overwriting the stored config with defaults
- Slider `vadThreshold` only fires on pointer-up (shadcn behavior), so writes are infrequent

### 1.4 Frontend Cleanup

**`src/routes/recording.tsx`** — remove `chunk_duration_ms: 500` from `buildConfig()`:

```tsx
function buildConfig(panel: RecordingPanelConfig): RealtimeConfig {
  return {
    device_id: panel.deviceId || null,
    language: panel.language === 'auto' ? null : panel.language || null,
    mode: panel.mode === 'transcribe_and_translate'
      ? { transcribe_and_translate: { target_language: panel.targetLang } }
      : panel.mode,
    vad_threshold: panel.vadThreshold,
    // chunk_duration_ms removed — field no longer exists in RealtimeConfig
  }
}
```

**`src/components/recording/RecordingMain.tsx`** — remove `chunk_duration_ms: 500` from `DEFAULT_CONFIG`.

**`src/store/settings.ts`** — remove `audio_chunk_ms` from the TypeScript AppConfig mirror type and default object.

**`src/components/layout/__tests__/integration.test.tsx`** — remove `audio_chunk_ms: 500` from the AppConfig test fixture.

---

## Feature 2: Latency Reduction

### 2.1 Pipeline Parameters — `src-tauri/src/transcription/pipeline.rs`

```rust
// Before:
const PAUSE_FLUSH_MS: u64 = 800;
// tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

// After:
const PAUSE_FLUSH_MS: u64 = 500;   // saves 300ms per sentence
// tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;  // saves ~40ms
```

**Rationale**: 500ms matches the lower bound of natural inter-sentence pauses in Chinese speech. Research (WhisperLive, Deepgram) shows <300ms is needed to split at word level; 500ms is safe for sentence-level segmentation.

### 2.2 VAD Cold-Start Window — `src-tauri/src/audio/vad.rs`

```rust
// Before:
const NOISE_FLOOR_WINDOW: usize = 50;  // 50 × 100ms = 5s calibration

// After:
const NOISE_FLOOR_WINDOW: usize = 25;  // 25 × 100ms = 2.5s calibration
```

**Rationale**: P25 over 25 silence frames is statistically sufficient for a stable noise floor estimate in a typical office environment. Halving the window reduces the first-segment visible delay by ~2.5s at the cost of marginally less smoothing.

### 2.3 Frontend Poll Frequency — `src/store/recording.ts`

```ts
// Before: every 300ms
if (tickCount % 3 === 0 && currentSession) {

// After: every 200ms
if (tickCount % 2 === 0 && currentSession) {
```

### Latency Impact Summary

| Source | Before | After | Δ |
|--------|--------|-------|---|
| Pause trigger | 800ms | 500ms | −300ms |
| Loop check granularity | 50ms | 10ms | −40ms |
| Frontend poll | 300ms | 200ms | −100ms |
| VAD cold-start (first segment only) | 5s | 2.5s | −2.5s |
| Whisper inference | ~400ms | ~400ms | 0 |
| **Steady-state total** | **~1.8s** | **~1.2s** | **−600ms** |

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| `updateConfig` fails (DB error) | Log to console, no UI disruption — setting reverts on next launch |
| Last-used device not found in device list | Fall back to system default silently |
| `getConfig` fails on mount | Component uses hardcoded defaults (same as before) |
| PAUSE_FLUSH_MS=500ms splits a sentence | Audio accumulates into next segment; Whisper context window handles cross-segment continuity |
| NOISE_FLOOR_WINDOW=25 inaccurate in noisy env | `clamp(max=0.040)` prevents over-filtering; 25-frame P25 still better than fixed threshold |

---

## Files Changed

| File | Change Type | Summary |
|------|-------------|---------|
| `src-tauri/src/config/schema.rs` | Modify | Add `last_used_device_id`; remove `audio_chunk_ms` |
| `src-tauri/src/commands/transcription.rs` | Modify | Remove `chunk_duration_ms` from `RealtimeConfig` |
| `src-tauri/src/transcription/pipeline.rs` | Modify | PAUSE_FLUSH_MS=500, loop sleep=10ms |
| `src-tauri/src/audio/vad.rs` | Modify | NOISE_FLOOR_WINDOW=25 |
| `src/store/recording.ts` | Modify | tickCount % 2 |
| `src/components/recording/RecordingPanel.tsx` | Modify | Full read+save for all 6 settings |
| `src/components/recording/RecordingMain.tsx` | Modify | Remove chunk_duration_ms from DEFAULT_CONFIG |
| `src/routes/recording.tsx` | Modify | Remove chunk_duration_ms from buildConfig |
| `src/store/settings.ts` | Modify | Remove audio_chunk_ms field and default |
| `src/components/layout/__tests__/integration.test.tsx` | Modify | Remove audio_chunk_ms from test fixture |

No new files. No DB schema changes. `src/lib/bindings.ts` regenerated automatically at debug build.

---

## Testing Plan

1. **Settings persistence** — Start app, set language=zh, mode=transcribe_only, specific microphone; close and reopen → verify all 6 settings restore. Unplug the saved microphone → verify fallback to system default.
2. **Dead code removal** — `cargo check` passes; `npm run typecheck` passes; all existing tests pass.
3. **Latency measurement** — Record 5s of Chinese speech, pause 1s. Measure time from pause end to text appearance. Target: <1.5s.
4. **VAD calibration** — Start recording immediately after clicking Start; verify first segment appears within 3s (not 6s).
5. **Regression: pause detection** — Speak continuously for 30s without pause; verify 25s safety flush still triggers correctly.
