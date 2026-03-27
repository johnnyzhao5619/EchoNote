use echonote_lib::workspace::document::{DocumentDetail, FolderNode, SearchResult, TextAsset};

#[test]
fn workspace_document_types_are_constructible() {
    let node = FolderNode {
        id: "folder-1".to_string(),
        name: "Notes".to_string(),
        parent_id: None,
        folder_kind: "user".to_string(),
        is_system: false,
        document_count: 2,
        children: vec![],
    };

    let detail = DocumentDetail {
        id: "doc-1".to_string(),
        title: "Meeting".to_string(),
        folder_id: Some(node.id.clone()),
        source_type: "note".to_string(),
        recording_id: None,
        assets: vec![TextAsset {
            id: "asset-1".to_string(),
            role: "document_text".to_string(),
            language: Some("zh-CN".to_string()),
            content: "EchoNote".to_string(),
            updated_at: 1,
        }],
        created_at: 1,
        updated_at: 2,
    };

    let result = SearchResult {
        document_id: detail.id.clone(),
        title: detail.title.clone(),
        snippet: "<mark>EchoNote</mark>".to_string(),
        rank: -1.0,
        folder_id: detail.folder_id.clone(),
        updated_at: detail.updated_at,
    };

    assert_eq!(result.document_id, "doc-1");
    assert_eq!(detail.assets.len(), 1);
}
