# Adaptive VAD + Pause-Based Segmentation Design

**Date**: 2026-03-21
**Status**: Approved
**Scope**: `src-tauri/src/audio/vad.rs`, `src-tauri/src/transcription/pipeline.rs`, `src-tauri/src/transcription/engine.rs`, `src/components/recording/RecordingMain.tsx`, `src/store/recording.ts`, `src/components/recording/RecordingPanel.tsx`

---

## Problem

Real-time recording produces no transcription output during recording (only after stop). Root causes:

1. **Fixed VAD threshold (0.010–0.015) filters out iPhone microphone audio** (RMS ≈ 0.005–0.020). When level is below threshold, no `AudioChunk` reaches the pipeline.
2. **No intermediate flush mechanism**: pipeline only flushes at 30s accumulation or 3s channel silence. Sporadic VAD-passing frames continuously reset `last_audio_at`, preventing the silence flush from triggering.
3. **Flush blocks the pipeline loop**: `flush_to_whisper` is `await`ed inside the main loop, so no new audio can be accumulated while Whisper is running.
4. **Waveform display uses `sqrt(level * 50)` gain**, making 0.014 RMS appear as 85% bar height — misleading users and developers about actual signal strength.

---

## Goals

- Transcription text appears within ~1–2 seconds after a natural speech pause
- No manual VAD threshold tuning required for different microphones (iPhone, built-in, external)
- New audio continues to accumulate while the previous segment is being transcribed
- Sentence-level granularity (pause-driven), not fixed-interval

---

## Architecture

### Data Flow (New)

```
Microphone → resampler → VadFilter (adaptive threshold, noise floor tracking)
    → transcription_tx.try_send(AudioChunk)
    → Pipeline loop (try_recv + sleep 50ms)
    ├── Step 1: collect completed inference results (non-blocking)
    ├── Step 2: process TranscriptionCommands
    ├── Step 3: check flush conditions
    │     Condition A (pause): last_audio_at.elapsed() >= 800ms && active_buf >= 0.5s
    │     Condition B (safety): active_buf >= 25s
    │     → tokio::spawn(run_inference) — non-blocking, loop continues
    └── Step 4: sleep 50ms

run_inference (background task):
    → spawn_blocking → WhisperEngine::transcribe (serialized via Mutex)
    → result_tx.send(InferenceResult)

Pipeline loop Step 1 receives result:
    → segments_cache.insert
    → inference_in_flight = false
```

### Key Parameters

| Parameter | Old | New | Source |
|-----------|-----|-----|--------|
| Pause trigger | 3000ms | **800ms** | WhisperLive Chinese practice |
| Min infer length | none | **8000 samples (0.5s)** | faster-whisper min_speech |
| Max accumulation | 30s | **25s** | Leave 5s buffer before Whisper 30s limit |
| VAD threshold | fixed 0.010 | **adaptive: noise_floor × 4.0** | whisper-live multiplier |
| Noise floor window | none | **50 frames (P25)** | silero-vad EMA approach |
| Inference blocking | await in loop | **tokio::spawn (async)** | double-buffer core |

---

## Component Designs

### 1. VadFilter — Adaptive Threshold (`vad.rs`)

**New fields:**
```rust
rms_history: VecDeque<f32>,   // sliding window, capacity 50
adaptive_threshold: f32,       // current dynamic threshold, starts at initial value
base_multiplier: f32,          // = 4.0
```

**Algorithm:**

```
Phase 1 — Cold start (frames 1–49):
  Use initial threshold (0.008 default)
  Collect RMS into rms_history for every silence frame

Phase 2 — Stable (frame 50+):
  noise_floor = P25(rms_history)  ← sort, take index 12
  adaptive_threshold = clamp(noise_floor × 4.0, min=0.003, max=0.040)

Phase 3 — Continuous tracking:
  Only update rms_history when rms < adaptive_threshold (silence frames only)
  Prevents speech peaks from polluting noise estimate
```

**Constraints:**
- Lower bound 0.003: prevents over-sensitivity in very quiet environments
- Upper bound 0.040: prevents filtering all speech in noisy environments
- Multiplier 4.0: speech RMS is typically 4–8× noise floor

**Public interface unchanged:** `VadFilter::new(threshold, on_level)` — `threshold` becomes the cold-start initial value. `set_threshold()` retained for manual override.

**Diagnostic log enhanced:**
```
[vad] chunk #50: rms=0.0144, noise_floor=0.0036, threshold=0.0144(adapted) → VOICE
```

---

### 2. TranscriptionWorker — Double Buffer + Async Inference (`pipeline.rs`)

**New state:**
```rust
active_buf: Vec<f32>              // accumulating new audio
inference_in_flight: bool         // background task running
result_tx: mpsc::SyncSender<InferenceResult>   // channel back from inference tasks
result_rx: mpsc::Receiver<InferenceResult>
```

**InferenceResult type:**
```rust
struct InferenceResult {
    session_id: String,
    segments: Vec<SegmentPayload>,
}
```

**Loop structure:**
```
Each iteration:
  Step 1: result_rx.try_recv()
    Ok(result) → write segments_cache, inference_in_flight = false
    Err(Empty)  → ignore

  Step 2: rx.try_recv() for TranscriptionCommand
    Start   → reset active_buf, counters, last_audio_at; inference_in_flight = false
    AudioChunk → active_buf.extend(chunk); last_audio_at = Instant::now()
    Pause/Resume → existing logic
    Stop    → drain pending result, sync-await flush of active_buf, send done_tx

  Step 3: flush check (only when !paused && session_id.is_some() && !inference_in_flight)
    Condition A: last_audio_at.elapsed() >= PAUSE_FLUSH_MS && active_buf.len() >= MIN_INFER_SAMPLES
    Condition B: active_buf.len() >= MAX_ACCUM_SAMPLES
    → audio = mem::take(&mut active_buf)
    → inference_in_flight = true
    → tokio::spawn(run_inference(audio, ...))

  Step 4: tokio::time::sleep(50ms)
```

**Updated constants:**
```rust
const MAX_ACCUM_SAMPLES: usize = 16_000 * 25;  // 25s safety flush
const PAUSE_FLUSH_MS: u64 = 800;               // 800ms pause → sentence boundary
const MIN_INFER_SAMPLES: usize = 8_000;        // 0.5s minimum
```

**Stop handling (ordered):**
```
1. If inference_in_flight: wait on result_rx (30s timeout), write result to cache
2. If active_buf non-empty: sync await flush_to_whisper (final segment, ordered)
3. session_id = None; send done_tx
```

**Panic safety:** `run_inference` always sends to `result_tx` even on error (empty segments), ensuring `inference_in_flight` is always cleared.

**result_tx capacity:** `sync_channel(4)` — Whisper Mutex serializes inference, so at most 1 result is ever in-flight. Capacity 4 is a safety margin.

---

### 3. WhisperEngine — Hallucination Suppression (`engine.rs`)

Add one missing parameter identified in research:

```rust
params.set_compression_ratio_thold(2.4);  // filter repeated-text hallucinations (whisper.cpp default)
```

Existing parameters already correct:
- `set_no_speech_thold(0.6)` ✓
- `set_logprob_thold(-1.0)` ✓

---

### 4. Frontend Changes

#### `RecordingMain.tsx` — Waveform display

```tsx
// Old: sqrt amplification (misleading)
const displayLevel = Math.min(1, Math.sqrt(level * 50))

// New: linear with 10x gain (iPhone 0.015 → 15%, clear speech 0.05 → 50%)
const displayLevel = Math.min(1, level * 10)
```

Add VAD threshold reference line on canvas (dashed horizontal line), requires passing `vadThreshold` as prop to `AudioWaveform`.

#### `RecordingMain.tsx` — Calibration status text

```tsx
{status === 'recording' && segments.length === 0 && elapsed < 5000
  ? 'Calibrating microphone...'
  : status !== 'idle'
  ? 'Listening...'
  : 'Press Start Recording to begin'}
```

#### `RecordingPanel.tsx` — VAD defaults

```tsx
// Default: 0.010 → 0.008
const [vadThreshold, setVadThreshold] = useState<number>(0.008)

// Clamp: 0.020 → 0.015
setVadThreshold(Math.min(cfg.vad_threshold, 0.015))
```

#### `store/recording.ts` — Poll frequency

```ts
// Segments poll: every 500ms → 300ms
if (tickCount % 3 === 0 && currentSession) {
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| `run_inference` panics | Always sends empty `InferenceResult` to `result_tx`; `inference_in_flight` cleared |
| Stop with inference in-flight | Wait `result_rx` up to 30s; timeout → log warning, proceed with `done_tx` |
| Noise floor drifts (environment change) | EMA tracking with 2.5s time constant; `clamp(max=0.040)` prevents over-filtering |
| No pause > 800ms (fast continuous speech) | 25s safety flush triggers; entire segment processed at once (better quality) |
| Audio < 0.5s after pause | `MIN_INFER_SAMPLES` guard skips inference; audio discarded or merged into next buffer |
| `result_tx` full (capacity 4) | `try_send` fails silently; Whisper Mutex ensures this never happens in practice |

---

## Files Changed

| File | Change Type | Summary |
|------|-------------|---------|
| `src-tauri/src/audio/vad.rs` | Modify | Add adaptive threshold fields and P25 noise floor algorithm |
| `src-tauri/src/transcription/pipeline.rs` | Modify | Double buffer, async inference, 800ms pause trigger |
| `src-tauri/src/transcription/engine.rs` | Modify | Add `compression_ratio_thold(2.4)` |
| `src/components/recording/RecordingMain.tsx` | Modify | Linear waveform gain, VAD threshold line, calibration text |
| `src/store/recording.ts` | Modify | Poll frequency 500ms → 300ms |
| `src/components/recording/RecordingPanel.tsx` | Modify | Default threshold 0.008, clamp 0.015 |

No new files. No new Tauri commands. No schema changes.

---

## Testing Plan

1. **Unit: `VadFilter` adaptive threshold** — Feed 50 frames of known RMS (noise_floor = 0.005), verify `adaptive_threshold` converges to 0.005 × 4.0 = 0.020; verify clamp behavior at extremes
2. **Unit: Pipeline pause detection** — Mock `AudioChunk` stream with 800ms gap, verify `run_inference` is called; verify `inference_in_flight` prevents double-trigger
3. **Integration: iPhone mic** — Record 30s of Chinese speech with iPhone as Continuity Camera mic, verify segments appear during recording (not just on stop)
4. **Edge: No pause** — Read text continuously for 30s without pause, verify 25s safety flush produces output
5. **Edge: Stop during inference** — Start recording, speak, wait for inference to start (check `inference_in_flight`), immediately stop — verify all segments are saved to DB
