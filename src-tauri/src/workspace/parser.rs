use std::collections::HashMap;
use std::path::Path;

use crate::error::AppError;
use crate::workspace::document::ParsedDocument;

pub fn parse_file(file_path: &Path) -> Result<ParsedDocument, AppError> {
    let ext = file_path
        .extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| ext.to_lowercase())
        .unwrap_or_default();

    match ext.as_str() {
        "pdf" => parse_pdf(file_path),
        "docx" => parse_docx(file_path),
        "txt" | "md" => parse_text(file_path),
        _ => Err(AppError::Workspace(format!("unsupported file type: .{ext}"))),
    }
}

fn parse_pdf(path: &Path) -> Result<ParsedDocument, AppError> {
    let bytes = std::fs::read(path)?;
    let text = pdf_extract::extract_text_from_mem(&bytes)
        .map_err(|err| AppError::Workspace(format!("pdf parse error: {err}")))?;

    let mut metadata = HashMap::new();
    metadata.insert("source".to_string(), "pdf".to_string());
    metadata.insert("file_path".to_string(), path.to_string_lossy().to_string());

    Ok(ParsedDocument {
        title: file_stem(path),
        text,
        metadata,
    })
}

fn parse_docx(path: &Path) -> Result<ParsedDocument, AppError> {
    use docx_rs::{read_docx, DocumentChild, ParagraphChild, RunChild};

    let bytes = std::fs::read(path)?;
    let docx = read_docx(&bytes).map_err(|err| AppError::Workspace(format!("docx parse error: {err:?}")))?;

    let mut lines = Vec::new();
    for child in &docx.document.children {
        if let DocumentChild::Paragraph(paragraph) = child {
            let mut line = String::new();
            for run in &paragraph.children {
                if let ParagraphChild::Run(run) = run {
                    for child in &run.children {
                        if let RunChild::Text(text) = child {
                            line.push_str(&text.text);
                        }
                    }
                }
            }
            if !line.is_empty() {
                lines.push(line);
            }
        }
    }

    let mut metadata = HashMap::new();
    metadata.insert("source".to_string(), "docx".to_string());
    metadata.insert("file_path".to_string(), path.to_string_lossy().to_string());

    Ok(ParsedDocument {
        title: file_stem(path),
        text: lines.join("\n"),
        metadata,
    })
}

fn parse_text(path: &Path) -> Result<ParsedDocument, AppError> {
    let text = std::fs::read_to_string(path)?;
    let ext = path
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("txt")
        .to_lowercase();

    let mut metadata = HashMap::new();
    metadata.insert("source".to_string(), ext);
    metadata.insert("file_path".to_string(), path.to_string_lossy().to_string());

    Ok(ParsedDocument {
        title: file_stem(path),
        text,
        metadata,
    })
}

fn file_stem(path: &Path) -> String {
    path.file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or("Untitled")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::parse_file;
    use std::io::Write;

    fn write_temp_file(ext: &str, content: &str) -> tempfile::NamedTempFile {
        let mut file = tempfile::Builder::new().suffix(ext).tempfile().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        file
    }

    #[test]
    fn parse_file_reads_plain_text_inputs() {
        let file = write_temp_file(".txt", "Hello, EchoNote!");
        let parsed = parse_file(file.path()).unwrap();
        assert_eq!(parsed.text, "Hello, EchoNote!");
        assert_eq!(parsed.metadata["source"], "txt");
    }
}
