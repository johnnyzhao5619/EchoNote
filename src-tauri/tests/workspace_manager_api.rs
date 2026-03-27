use echonote_lib::storage::db::Database;
use echonote_lib::workspace::manager::WorkspaceManager;

#[tokio::test]
async fn workspace_manager_can_create_and_search_documents() {
    let db = Database::open("sqlite::memory:").await.unwrap();
    let manager = WorkspaceManager::new(db.pool.clone());

    let folder = manager.create_folder("Notes", None).await.unwrap();
    let doc = manager
        .create_document("Launch Plan", Some(&folder.id), "note", None)
        .await
        .unwrap();

    manager
        .upsert_text_asset(&doc.id, "document_text", "Launch v3 planning notes", None)
        .await
        .unwrap();

    let results = manager.search_documents("launch v3").await.unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].document_id, doc.id);
}
