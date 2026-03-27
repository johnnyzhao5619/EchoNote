use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use specta::Type;
use tauri::{AppHandle, Emitter};
use tokio::sync::{mpsc, Mutex};
use uuid::Uuid;

use crate::error::AppError;
use crate::storage::db::Database;
use crate::transcription::engine::{RawSegment, WhisperEngine};
use crate::transcription::ffmpeg::{convert_to_wav, detect_ffmpeg, is_supported_format, needs_transcode};

#[derive(Debug, Clone, Serialize, Deserialize, Type, PartialEq)]
#[serde(tag = "type", content = "data")]
pub enum BatchStatus {
    Queued,
    Processing { progress: f32 },
    Done { recording_id: String, document_id: String },
    Failed { error: String },
    Cancelled,
}

#[derive(Debug, Clone)]
pub struct BatchJob {
    pub id: String,
    pub file_path: PathBuf,
    pub file_name: String,
    pub language: Option<String>,
    pub status: BatchStatus,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct BatchJobView {
    pub job_id: String,
    pub file_name: String,
    pub language: Option<String>,
    pub status: BatchStatus,
    pub created_at: i64,
}

pub enum BatchCommand {
    Enqueue {
        job_id: String,
        file_path: PathBuf,
        language: Option<String>,
    },
    Cancel {
        job_id: String,
    },
    ClearCompleted,
}

pub struct BatchQueue {
    jobs: Arc<Mutex<Vec<BatchJob>>>,
    pending: Arc<Mutex<VecDeque<String>>>,
    current_job_id: Arc<Mutex<Option<String>>>,
    cancel_flag: Arc<Mutex<bool>>,
}

impl BatchQueue {
    pub fn new() -> Self {
        Self {
            jobs: Arc::new(Mutex::new(Vec::new())),
            pending: Arc::new(Mutex::new(VecDeque::new())),
            current_job_id: Arc::new(Mutex::new(None)),
            cancel_flag: Arc::new(Mutex::new(false)),
        }
    }

    pub async fn run(
        self: Arc<Self>,
        mut rx: mpsc::Receiver<BatchCommand>,
        app_handle: AppHandle,
        db: Arc<Database>,
        whisper_engine: Arc<std::sync::Mutex<Option<WhisperEngine>>>,
    ) {
        let mut active_job: Option<tokio::task::JoinHandle<()>> = None;
        let mut receiver_closed = false;

        loop {
            if let Some(handle) = active_job.as_mut() {
                if receiver_closed {
                    let _ = handle.await;
                    break;
                }

                tokio::select! {
                    maybe_cmd = rx.recv() => {
                        match maybe_cmd {
                            Some(cmd) => self.handle_command(cmd, &app_handle).await,
                            None => receiver_closed = true,
                        }
                    }
                    join_result = handle => {
                        if let Err(error) = join_result {
                            log::error!("[batch] worker join error: {error}");
                        }
                        active_job = None;
                    }
                }

                continue;
            }

            if receiver_closed {
                break;
            }

            while let Ok(cmd) = rx.try_recv() {
                self.handle_command(cmd, &app_handle).await;
            }

            let next_job_id = {
                let mut pending = self.pending.lock().await;
                pending.pop_front()
            };

            if let Some(job_id) = next_job_id {
                let queue = Arc::clone(&self);
                let app_handle = app_handle.clone();
                let db = Arc::clone(&db);
                let whisper_engine = Arc::clone(&whisper_engine);

                active_job = Some(tokio::spawn(async move {
                    queue
                        .execute_job(&job_id, &app_handle, &db, &whisper_engine)
                        .await;
                }));
                continue;
            }

            match rx.recv().await {
                Some(cmd) => self.handle_command(cmd, &app_handle).await,
                None => receiver_closed = true,
            }
        }
    }

    async fn handle_command(&self, cmd: BatchCommand, app_handle: &AppHandle) {
        match cmd {
            BatchCommand::Enqueue {
                job_id,
                file_path,
                language,
            } => {
                let file_name = file_path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or("unknown")
                    .to_string();

                if !is_supported_format(&file_path) {
                    self.emit_error(
                        app_handle,
                        &job_id,
                        &file_name,
                        "Unsupported file format",
                    );
                    return;
                }

                let created_at = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as i64;

                let job = BatchJob {
                    id: job_id.clone(),
                    file_path,
                    file_name: file_name.clone(),
                    language,
                    status: BatchStatus::Queued,
                    created_at,
                };

                self.jobs.lock().await.push(job);
                self.pending.lock().await.push_back(job_id.clone());

                let _ = app_handle.emit(
                    "batch:queued",
                    serde_json::json!({
                        "job_id": job_id,
                        "file_name": file_name,
                    }),
                );
            }
            BatchCommand::Cancel { job_id } => {
                let mut jobs = self.jobs.lock().await;
                if let Some(job) = jobs.iter_mut().find(|job| job.id == job_id) {
                    match &job.status {
                        BatchStatus::Queued => {
                            let mut pending = self.pending.lock().await;
                            pending.retain(|pending_job_id| pending_job_id != &job_id);
                            job.status = BatchStatus::Cancelled;
                        }
                        BatchStatus::Processing { .. } => {
                            *self.cancel_flag.lock().await = true;
                        }
                        _ => {}
                    }
                }
            }
            BatchCommand::ClearCompleted => {
                let mut jobs = self.jobs.lock().await;
                jobs.retain(|job| {
                    !matches!(
                        &job.status,
                        BatchStatus::Done { .. }
                            | BatchStatus::Failed { .. }
                            | BatchStatus::Cancelled
                    )
                });
            }
        }
    }

    async fn execute_job(
        &self,
        job_id: &str,
        app_handle: &AppHandle,
        db: &Arc<Database>,
        whisper_engine: &Arc<std::sync::Mutex<Option<WhisperEngine>>>,
    ) {
        let (file_path, file_name, language) = {
            let jobs = self.jobs.lock().await;
            let Some(job) = jobs.iter().find(|job| job.id == job_id) else {
                return;
            };

            (
                job.file_path.clone(),
                job.file_name.clone(),
                job.language.clone(),
            )
        };

        *self.current_job_id.lock().await = Some(job_id.to_string());
        *self.cancel_flag.lock().await = false;
        self.update_progress(job_id, 0.0).await;
        self.emit_progress(app_handle, job_id, &file_name, 0.0);

        let (wav_path, _temp_file) = if needs_transcode(&file_path) {
            if !detect_ffmpeg() {
                let _ = app_handle.emit("batch:ffmpeg_missing", ());
                self.mark_failed(job_id, "ffmpeg not found in PATH").await;
                self.emit_error(
                    app_handle,
                    job_id,
                    &file_name,
                    "ffmpeg not found. Please install ffmpeg.",
                );
                self.finish_job().await;
                return;
            }

            let temp_file = match tempfile::Builder::new()
                .prefix(&format!("echonote-{}", Uuid::new_v4()))
                .suffix(".wav")
                .tempfile()
            {
                Ok(file) => file,
                Err(error) => {
                    self.mark_failed(job_id, &error.to_string()).await;
                    self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                    self.finish_job().await;
                    return;
                }
            };

            let temp_path = temp_file.path().to_path_buf();
            let input_path = file_path.clone();
            let output_path = temp_path.clone();

            match tokio::task::spawn_blocking(move || convert_to_wav(&input_path, &output_path)).await
            {
                Ok(Ok(())) => (temp_path, Some(temp_file)),
                Ok(Err(error)) => {
                    self.mark_failed(job_id, &error.to_string()).await;
                    self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                    self.finish_job().await;
                    return;
                }
                Err(error) => {
                    self.mark_failed(job_id, &error.to_string()).await;
                    self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                    self.finish_job().await;
                    return;
                }
            }
        } else {
            (file_path.clone(), None)
        };

        self.update_progress(job_id, 0.2).await;
        self.emit_progress(app_handle, job_id, &file_name, 0.2);

        let wav_path_for_decode = wav_path.clone();
        let pcm_result = tokio::task::spawn_blocking(move || decode_wav_to_pcm(&wav_path_for_decode)).await;

        let pcm = match pcm_result {
            Ok(Ok(samples)) => samples,
            Ok(Err(error)) => {
                self.mark_failed(job_id, &error).await;
                self.emit_error(app_handle, job_id, &file_name, &error);
                self.finish_job().await;
                return;
            }
            Err(error) => {
                self.mark_failed(job_id, &error.to_string()).await;
                self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                self.finish_job().await;
                return;
            }
        };

        self.update_progress(job_id, 0.3).await;
        self.emit_progress(app_handle, job_id, &file_name, 0.3);

        if self.consume_cancel_flag().await {
            self.mark_cancelled(job_id).await;
            self.finish_job().await;
            return;
        }

        let language_for_transcribe = language.clone();
        let engine = Arc::clone(whisper_engine);
        let transcribe_result = tokio::task::spawn_blocking(move || -> Result<Vec<RawSegment>, AppError> {
            let guard = engine
                .lock()
                .map_err(|_| AppError::Transcription("whisper engine poisoned".into()))?;
            let engine = guard
                .as_ref()
                .ok_or_else(|| AppError::Model("Whisper engine not loaded".into()))?;
            engine.transcribe(&pcm, language_for_transcribe.as_deref(), false)
        })
        .await;

        let segments = match transcribe_result {
            Ok(Ok(segments)) => segments,
            Ok(Err(error)) => {
                self.mark_failed(job_id, &error.to_string()).await;
                self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                self.finish_job().await;
                return;
            }
            Err(error) => {
                self.mark_failed(job_id, &error.to_string()).await;
                self.emit_error(app_handle, job_id, &file_name, &error.to_string());
                self.finish_job().await;
                return;
            }
        };

        self.update_progress(job_id, 0.9).await;
        self.emit_progress(app_handle, job_id, &file_name, 0.9);

        if self.consume_cancel_flag().await {
            self.mark_cancelled(job_id).await;
            self.finish_job().await;
            return;
        }

        match Self::persist_job(db, &file_path, &file_name, &segments, &language).await {
            Ok((recording_id, document_id)) => {
                {
                    let mut jobs = self.jobs.lock().await;
                    if let Some(job) = jobs.iter_mut().find(|job| job.id == job_id) {
                        job.status = BatchStatus::Done {
                            recording_id: recording_id.clone(),
                            document_id: document_id.clone(),
                        };
                    }
                }

                let _ = app_handle.emit(
                    "batch:done",
                    serde_json::json!({
                        "job_id": job_id,
                        "recording_id": recording_id,
                        "document_id": document_id,
                    }),
                );
            }
            Err(error) => {
                self.mark_failed(job_id, &error.to_string()).await;
                self.emit_error(app_handle, job_id, &file_name, &error.to_string());
            }
        }

        self.finish_job().await;
    }

    async fn persist_job(
        db: &Arc<Database>,
        file_path: &Path,
        file_name: &str,
        segments: &[RawSegment],
        language: &Option<String>,
    ) -> Result<(String, String), AppError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as i64;

        let recording_id = Uuid::new_v4().to_string();
        let document_id = Uuid::new_v4().to_string();
        let asset_id = Uuid::new_v4().to_string();
        let duration_ms = segments.last().map(|segment| segment.end_ms as i64).unwrap_or(0);
        let detected_language = segments.first().map(|segment| segment.language.clone());
        let language = language.clone().or(detected_language);
        let transcript = segments
            .iter()
            .map(|segment| segment.text.as_str())
            .collect::<Vec<_>>()
            .join(" ");

        let file_path_string = file_path.to_string_lossy().to_string();
        let mut tx = db.pool.begin().await?;

        sqlx::query(
            "INSERT INTO recordings (id, title, file_path, duration_ms, language, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind(&recording_id)
        .bind(file_name)
        .bind(&file_path_string)
        .bind(duration_ms)
        .bind(language.as_deref())
        .bind(now)
        .bind(now)
        .execute(&mut *tx)
        .await?;

        for segment in segments {
            sqlx::query(
                "INSERT INTO transcription_segments (recording_id, start_ms, end_ms, text, language)
                 VALUES (?, ?, ?, ?, ?)"
            )
            .bind(&recording_id)
            .bind(segment.start_ms as i64)
            .bind(segment.end_ms as i64)
            .bind(&segment.text)
            .bind(&segment.language)
            .execute(&mut *tx)
            .await?;
        }

        sqlx::query(
            "INSERT INTO workspace_documents (id, folder_id, title, source_type, recording_id, created_at, updated_at)
             VALUES (?, NULL, ?, 'recording', ?, ?, ?)"
        )
        .bind(&document_id)
        .bind(file_name)
        .bind(&recording_id)
        .bind(now)
        .bind(now)
        .execute(&mut *tx)
        .await?;

        if !transcript.is_empty() {
            sqlx::query(
                "INSERT INTO workspace_text_assets (id, document_id, role, language, content, created_at, updated_at)
                 VALUES (?, ?, 'transcript', ?, ?, ?, ?)"
            )
            .bind(&asset_id)
            .bind(&document_id)
            .bind(language.as_deref())
            .bind(&transcript)
            .bind(now)
            .bind(now)
            .execute(&mut *tx)
            .await?;
        }

        tx.commit().await?;
        Ok((recording_id, document_id))
    }

    async fn mark_failed(&self, job_id: &str, error: &str) {
        let mut jobs = self.jobs.lock().await;
        if let Some(job) = jobs.iter_mut().find(|job| job.id == job_id) {
            job.status = BatchStatus::Failed {
                error: error.to_string(),
            };
        }
    }

    async fn mark_cancelled(&self, job_id: &str) {
        let mut jobs = self.jobs.lock().await;
        if let Some(job) = jobs.iter_mut().find(|job| job.id == job_id) {
            job.status = BatchStatus::Cancelled;
        }
    }

    pub async fn get_all_jobs(&self) -> Vec<BatchJobView> {
        self.jobs
            .lock()
            .await
            .iter()
            .map(|job| BatchJobView {
                job_id: job.id.clone(),
                file_name: job.file_name.clone(),
                language: job.language.clone(),
                status: job.status.clone(),
                created_at: job.created_at,
            })
            .collect()
    }

    async fn update_progress(&self, job_id: &str, progress: f32) {
        let mut jobs = self.jobs.lock().await;
        if let Some(job) = jobs.iter_mut().find(|job| job.id == job_id) {
            job.status = BatchStatus::Processing { progress };
        }
    }

    async fn consume_cancel_flag(&self) -> bool {
        let mut cancel_flag = self.cancel_flag.lock().await;
        if *cancel_flag {
            *cancel_flag = false;
            true
        } else {
            false
        }
    }

    async fn finish_job(&self) {
        *self.cancel_flag.lock().await = false;
        *self.current_job_id.lock().await = None;
    }

    fn emit_error(&self, app_handle: &AppHandle, job_id: &str, file_name: &str, error: &str) {
        let _ = app_handle.emit(
            "batch:error",
            serde_json::json!({
                "job_id": job_id,
                "file_name": file_name,
                "error": error,
            }),
        );
    }

    fn emit_progress(&self, app_handle: &AppHandle, job_id: &str, file_name: &str, progress: f32) {
        let _ = app_handle.emit(
            "batch:progress",
            serde_json::json!({
                "job_id": job_id,
                "file_name": file_name,
                "progress": progress,
            }),
        );
    }
}

fn decode_wav_to_pcm(path: &Path) -> Result<Vec<f32>, String> {
    let mut reader = hound::WavReader::open(path).map_err(|error| error.to_string())?;
    let spec = reader.spec();

    match spec.sample_format {
        hound::SampleFormat::Float => reader
            .samples::<f32>()
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| error.to_string()),
        hound::SampleFormat::Int if spec.bits_per_sample <= 16 => reader
            .samples::<i16>()
            .map(|sample| sample.map(|value| value as f32 / i16::MAX as f32))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| error.to_string()),
        hound::SampleFormat::Int => reader
            .samples::<i32>()
            .map(|sample| sample.map(|value| value as f32 / i32::MAX as f32))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|error| error.to_string()),
    }
}
