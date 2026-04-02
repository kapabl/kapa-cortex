pub mod hasher;

use crate::db::Database;
use rusqlite::params;
use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Deserialize)]
struct ParseResult {
    symbols: Vec<ParsedSymbol>,
    imports: Vec<ParsedImport>,
    calls: Vec<ParsedCall>,
}

#[derive(Debug, Deserialize, Serialize)]
struct ParsedSymbol {
    name: String,
    kind: String,
    line: i64,
    scope: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct ParsedImport {
    raw: String,
    module: String,
    kind: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct ParsedCall {
    caller_function: String,
    callee_function: String,
    line: i64,
}

/// Index a single file. Checks content hash cache first.
pub fn index_file(db: &Database, file_path: &str) -> Result<(), String> {
    let content_hash = hasher::hash_file(file_path)?;

    db.with_conn(|conn| {
        index_file_with_conn(conn, file_path, &content_hash)
    })
}

fn index_file_with_conn(
    conn: &rusqlite::Connection,
    file_path: &str,
    content_hash: &str,
) -> Result<(), String> {
    // Check entry cache
    let cached = crate::db::queries::get_cached_entry(conn, content_hash)
        .map_err(|e| e.to_string())?;

    if cached {
        update_file_mapping(conn, file_path, content_hash)?;
        restore_from_cache(conn, file_path, content_hash)?;
        return Ok(());
    }

    // Cache miss — call Python parser
    let parse_result = call_python_parser(file_path)?;

    // Store in database
    conn.execute("DELETE FROM symbols WHERE file_path = ?", params![file_path])
        .map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM imports WHERE file_path = ?", params![file_path])
        .map_err(|e| e.to_string())?;
    conn.execute(
        "DELETE FROM calls WHERE caller_file = ?",
        params![file_path],
    )
    .map_err(|e| e.to_string())?;

    for sym in &parse_result.symbols {
        conn.execute(
            "INSERT INTO symbols (file_path, name, kind, line, scope) VALUES (?, ?, ?, ?, ?)",
            params![file_path, sym.name, sym.kind, sym.line, sym.scope],
        )
        .map_err(|e| e.to_string())?;
    }

    for imp in &parse_result.imports {
        conn.execute(
            "INSERT INTO imports (file_path, raw, module, kind) VALUES (?, ?, ?, ?)",
            params![file_path, imp.raw, imp.module, imp.kind],
        )
        .map_err(|e| e.to_string())?;
    }

    for call in &parse_result.calls {
        conn.execute(
            "INSERT INTO calls (caller_file, caller_function, callee_file, callee_function, line)
             VALUES (?, ?, '', ?, ?)",
            params![file_path, call.caller_function, call.callee_function, call.line],
        )
        .map_err(|e| e.to_string())?;
    }

    // Store in entry cache
    let symbols_blob = rmp_serde::to_vec(&parse_result.symbols).map_err(|e| e.to_string())?;
    let imports_blob = rmp_serde::to_vec(&parse_result.imports).map_err(|e| e.to_string())?;
    let calls_blob = rmp_serde::to_vec(&parse_result.calls).map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT OR REPLACE INTO entry_cache (content_hash, symbols, imports, calls) VALUES (?, ?, ?, ?)",
        params![content_hash, symbols_blob, imports_blob, calls_blob],
    )
    .map_err(|e| e.to_string())?;

    update_file_mapping(conn, file_path, content_hash)?;

    Ok(())
}

fn update_file_mapping(conn: &rusqlite::Connection, file_path: &str, content_hash: &str) -> Result<(), String> {
    conn
        .execute(
            "INSERT OR REPLACE INTO files (path, content_hash) VALUES (?, ?)",
            params![file_path, content_hash],
        )
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn restore_from_cache(conn: &rusqlite::Connection, file_path: &str, content_hash: &str) -> Result<(), String> {
    // Clear old data for this file
    conn.execute("DELETE FROM symbols WHERE file_path = ?", params![file_path])
        .map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM imports WHERE file_path = ?", params![file_path])
        .map_err(|e| e.to_string())?;
    conn.execute("DELETE FROM calls WHERE caller_file = ?", params![file_path])
        .map_err(|e| e.to_string())?;

    // Load from cache
    let (symbols_blob, imports_blob, calls_blob): (Vec<u8>, Vec<u8>, Vec<u8>) = conn
        .query_row(
            "SELECT symbols, imports, calls FROM entry_cache WHERE content_hash = ?",
            params![content_hash],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .map_err(|e| e.to_string())?;

    let symbols: Vec<ParsedSymbol> =
        rmp_serde::from_slice(&symbols_blob).map_err(|e| e.to_string())?;
    let imports: Vec<ParsedImport> =
        rmp_serde::from_slice(&imports_blob).map_err(|e| e.to_string())?;
    let calls: Vec<ParsedCall> =
        rmp_serde::from_slice(&calls_blob).map_err(|e| e.to_string())?;

    for sym in &symbols {
        conn.execute(
            "INSERT INTO symbols (file_path, name, kind, line, scope) VALUES (?, ?, ?, ?, ?)",
            params![file_path, sym.name, sym.kind, sym.line, sym.scope],
        )
        .map_err(|e| e.to_string())?;
    }

    for imp in &imports {
        conn.execute(
            "INSERT INTO imports (file_path, raw, module, kind) VALUES (?, ?, ?, ?)",
            params![file_path, imp.raw, imp.module, imp.kind],
        )
        .map_err(|e| e.to_string())?;
    }

    for call in &calls {
        conn.execute(
            "INSERT INTO calls (caller_file, caller_function, callee_file, callee_function, line)
             VALUES (?, ?, '', ?, ?)",
            params![file_path, call.caller_function, call.callee_function, call.line],
        )
        .map_err(|e| e.to_string())?;
    }

    Ok(())
}

fn call_python_parser(file_path: &str) -> Result<ParseResult, String> {
    let output = Command::new("python3")
        .args(["-m", "kapa_cortex.parse", file_path])
        .output()
        .map_err(|e| format!("Failed to run parser: {}", e))?;

    if !output.status.success() {
        return Err(format!(
            "Parser failed for {}: {}",
            file_path,
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Failed to parse output for {}: {}", file_path, e))
}
