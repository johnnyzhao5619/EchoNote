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

#[tokio::test]
async fn workspace_manager_can_list_all_documents_across_folders() {
    let db = Database::open("sqlite::memory:").await.unwrap();
    let manager = WorkspaceManager::new(db.pool.clone());

    let folder = manager.create_folder("Meetings", None).await.unwrap();
    let root_doc = manager
        .create_document("Root Note", None, "manual", None)
        .await
        .unwrap();
    let nested_doc = manager
        .create_document("Nested Note", Some(&folder.id), "manual", None)
        .await
        .unwrap();

    let docs = manager.list_all_documents().await.unwrap();
    let ids: Vec<String> = docs.into_iter().map(|doc| doc.id).collect();

    assert!(ids.contains(&root_doc.id));
    assert!(ids.contains(&nested_doc.id));
}
