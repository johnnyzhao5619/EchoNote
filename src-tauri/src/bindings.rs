use std::path::Path;

use tauri_specta::{collect_commands, Builder};

use crate::commands::{
    audio as audio_cmds,
    llm as llm_cmds,
    models as model_cmds,
    settings,
    theme,
    transcription as transcription_cmds,
    workspace as workspace_cmds,
};

pub fn builder() -> Builder<tauri::Wry> {
    Builder::<tauri::Wry>::new().commands(collect_commands![
        theme::get_current_theme,
        theme::set_current_theme,
        theme::list_builtin_themes,
        settings::get_config,
        settings::update_config,
        settings::reset_config,
        model_cmds::list_model_variants,
        model_cmds::download_model,
        model_cmds::cancel_download,
        model_cmds::delete_model,
        model_cmds::set_active_model,
        audio_cmds::list_audio_devices,
        transcription_cmds::start_realtime,
        transcription_cmds::pause_realtime,
        transcription_cmds::resume_realtime,
        transcription_cmds::stop_realtime,
        transcription_cmds::get_audio_level,
        transcription_cmds::get_realtime_segments,
        transcription_cmds::get_recording_status,
        transcription_cmds::check_ffmpeg_available,
        transcription_cmds::add_files_to_batch,
        transcription_cmds::get_batch_queue,
        transcription_cmds::cancel_batch_job,
        transcription_cmds::clear_completed_jobs,
        workspace_cmds::list_recordings,
        workspace_cmds::get_document_assets,
        workspace_cmds::ensure_document_for_recording,
        workspace_cmds::update_document_asset,
        workspace_cmds::delete_recording,
        workspace_cmds::list_folder_tree,
        workspace_cmds::create_folder,
        workspace_cmds::rename_folder,
        workspace_cmds::delete_folder,
        workspace_cmds::list_documents_in_folder,
        workspace_cmds::get_document,
        workspace_cmds::create_document,
        workspace_cmds::update_document,
        workspace_cmds::delete_document,
        workspace_cmds::search_workspace,
        workspace_cmds::export_document,
        workspace_cmds::import_file_to_workspace,
        llm_cmds::submit_llm_task,
        llm_cmds::cancel_llm_task,
        llm_cmds::get_llm_engine_status,
        llm_cmds::list_document_llm_tasks,
    ])
}

pub fn export_typescript_bindings(path: &Path) -> Result<(), specta_typescript::ExportError> {
    builder().export(
        &specta_typescript::Typescript::default()
            .bigint(specta_typescript::BigIntExportBehavior::Number)
            .header("// @ts-nocheck\n// Event payload types not in commands:\nexport type DownloadProgressPayload = { variant_id: string; downloaded_bytes: number; total_bytes: number | null; speed_bps: number; eta_secs: number | null }"),
        path,
    )
}
