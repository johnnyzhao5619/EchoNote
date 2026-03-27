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
    use crate::error::AppError;
    use docx_rs::{Docx, Paragraph, Run};
    use std::fs::File;
    use std::io::Write;
    use tempfile::NamedTempFile;

    fn write_temp_file(ext: &str, content: &str) -> NamedTempFile {
        let mut file = tempfile::Builder::new().suffix(ext).tempfile().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        file
    }

    fn write_temp_bytes(ext: &str, content: &[u8]) -> NamedTempFile {
        let mut file = tempfile::Builder::new().suffix(ext).tempfile().unwrap();
        file.write_all(content).unwrap();
        file
    }

    fn build_pdf_fixture(text: &str) -> Vec<u8> {
        let escaped = text
            .replace('\\', "\\\\")
            .replace('(', "\\(")
            .replace(')', "\\)");
        let stream = format!("BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET");
        let objects = [
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n".to_string(),
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n".to_string(),
            "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n".to_string(),
            "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".to_string(),
            format!(
                "5 0 obj\n<< /Length {} >>\nstream\n{stream}\nendstream\nendobj\n",
                stream.len()
            ),
        ];

        let mut pdf = b"%PDF-1.4\n".to_vec();
        let mut offsets = Vec::with_capacity(objects.len());

        for object in &objects {
            offsets.push(pdf.len());
            pdf.extend_from_slice(object.as_bytes());
        }

        let xref_offset = pdf.len();
        pdf.extend_from_slice(format!("xref\n0 {}\n", offsets.len() + 1).as_bytes());
        pdf.extend_from_slice(b"0000000000 65535 f \n");
        for offset in offsets {
            pdf.extend_from_slice(format!("{offset:010} 00000 n \n").as_bytes());
        }
        pdf.extend_from_slice(
            format!(
                "trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n",
                objects.len() + 1
            )
            .as_bytes(),
        );
        pdf
    }

    fn write_pdf_fixture(text: &str) -> NamedTempFile {
        write_temp_bytes(".pdf", &build_pdf_fixture(text))
    }

    fn write_docx_fixture(paragraphs: &[&str]) -> NamedTempFile {
        let file = tempfile::Builder::new().suffix(".docx").tempfile().unwrap();
        let writer = File::create(file.path()).unwrap();
        let docx = paragraphs.iter().fold(Docx::new(), |doc, paragraph| {
            doc.add_paragraph(Paragraph::new().add_run(Run::new().add_text(*paragraph)))
        });
        docx.build().pack(writer).unwrap();
        file
    }

    #[test]
    fn parse_file_reads_plain_text_inputs() {
        let file = write_temp_file(".txt", "Hello, EchoNote!");
        let parsed = parse_file(file.path()).unwrap();
        assert_eq!(parsed.text, "Hello, EchoNote!");
        assert_eq!(parsed.metadata["source"], "txt");
    }

    #[test]
    fn test_parse_md_preserves_markdown() {
        let markdown = "# Title\n\n**Bold** text and `code`.";
        let file = write_temp_file(".md", markdown);
        let parsed = parse_file(file.path()).unwrap();
        assert_eq!(parsed.text, markdown);
        assert_eq!(parsed.metadata["source"], "md");
    }

    #[test]
    fn test_parse_unsupported_extension_returns_error() {
        let file = write_temp_file(".xyz", "data");
        let err = parse_file(file.path());
        assert!(matches!(err, Err(AppError::Workspace(_))));
    }

    #[test]
    fn test_parse_pdf_extracts_text() {
        let file = write_pdf_fixture("EchoNote PDF fixture");
        let doc = parse_file(file.path()).unwrap();
        assert!(doc.text.contains("EchoNote PDF fixture"));
        assert_eq!(doc.metadata["source"], "pdf");
    }

    #[test]
    fn test_parse_docx_extracts_paragraphs() {
        let file = write_docx_fixture(&["EchoNote DOCX fixture", "Second paragraph"]);
        let doc = parse_file(file.path()).unwrap();
        assert_eq!(doc.text, "EchoNote DOCX fixture\nSecond paragraph");
        assert_eq!(doc.metadata["source"], "docx");
    }
}
