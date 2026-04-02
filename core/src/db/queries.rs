use rusqlite::{params, Connection};
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct SymbolDef {
    pub fqn: String,
    pub kind: String,
    pub file: String,
    pub line: i64,
}

#[derive(Debug, Serialize)]
pub struct Reference {
    pub file: String,
    pub line: i64,
}

#[derive(Debug, Serialize)]
pub struct CallerInfo {
    pub function: String,
    pub file: String,
    pub line: i64,
}

#[derive(Debug, Serialize)]
pub struct CalleeInfo {
    pub function: String,
    pub file: String,
    pub line: i64,
}

#[derive(Debug, Serialize)]
pub struct SymbolInfo {
    pub name: String,
    pub kind: String,
    pub line: i64,
    pub scope: String,
}

/// Find all definitions of a symbol across all scopes.
pub fn lookup(conn: &Connection, symbol: &str) -> rusqlite::Result<Vec<SymbolDef>> {
    let mut stmt = conn.prepare(
        "SELECT name, kind, file_path, line, scope FROM symbols WHERE name = ?",
    )?;
    let rows = stmt.query_map(params![symbol], |row| {
        let name: String = row.get(0)?;
        let kind: String = row.get(1)?;
        let file: String = row.get(2)?;
        let line: i64 = row.get(3)?;
        let scope: String = row.get(4)?;
        let fqn = if scope.is_empty() {
            name
        } else {
            format!("{}::{}", scope, name)
        };
        Ok(SymbolDef { fqn, kind, file, line })
    })?;
    rows.collect()
}

/// Find a scoped definition. Prefers header files.
pub fn find_scoped_definition(
    conn: &Connection,
    name: &str,
    scope: &str,
) -> rusqlite::Result<Option<(String, i64)>> {
    let mut stmt = conn.prepare(
        "SELECT file_path, line FROM symbols WHERE name = ? AND scope = ?",
    )?;
    let rows: Vec<(String, i64)> = stmt
        .query_map(params![name, scope], |row| {
            Ok((row.get(0)?, row.get(1)?))
        })?
        .collect::<Result<Vec<_>, _>>()?;

    // Prefer header files
    let header = rows.iter().find(|(f, _)| {
        f.ends_with(".h") || f.ends_with(".hpp") || f.ends_with(".hxx")
    });
    if let Some(result) = header {
        return Ok(Some(result.clone()));
    }
    Ok(rows.into_iter().next())
}

/// Get all callers of a function.
pub fn get_callers(
    conn: &Connection,
    function: &str,
    file: &str,
) -> rusqlite::Result<Vec<CallerInfo>> {
    let mut stmt = conn.prepare(
        "SELECT caller_function, caller_file, line FROM calls
         WHERE callee_function = ? AND callee_file = ?",
    )?;
    let rows = stmt.query_map(params![function, file], |row| {
        Ok(CallerInfo {
            function: row.get(0)?,
            file: row.get(1)?,
            line: row.get(2)?,
        })
    })?;
    rows.collect()
}

/// Get all callees of a function.
pub fn get_callees(
    conn: &Connection,
    function: &str,
    file: &str,
) -> rusqlite::Result<Vec<CalleeInfo>> {
    let mut stmt = conn.prepare(
        "SELECT callee_function, callee_file, line FROM calls
         WHERE caller_function = ? AND caller_file = ?",
    )?;
    let rows = stmt.query_map(params![function, file], |row| {
        Ok(CalleeInfo {
            function: row.get(0)?,
            file: row.get(1)?,
            line: row.get(2)?,
        })
    })?;
    rows.collect()
}

/// List all symbols in a file.
pub fn symbols_for_file(
    conn: &Connection,
    file_path: &str,
) -> rusqlite::Result<Vec<SymbolInfo>> {
    let mut stmt = conn.prepare(
        "SELECT name, kind, line, scope FROM symbols WHERE file_path = ? ORDER BY line",
    )?;
    let rows = stmt.query_map(params![file_path], |row| {
        Ok(SymbolInfo {
            name: row.get(0)?,
            kind: row.get(1)?,
            line: row.get(2)?,
            scope: row.get(3)?,
        })
    })?;
    rows.collect()
}

/// Get direct dependents of a file.
pub fn get_dependents(conn: &Connection, file_path: &str) -> rusqlite::Result<Vec<String>> {
    let mut stmt = conn.prepare("SELECT source FROM edges WHERE target = ?")?;
    let rows = stmt.query_map(params![file_path], |row| row.get(0))?;
    rows.collect()
}

/// Get direct dependencies of a file.
pub fn get_dependencies(conn: &Connection, file_path: &str) -> rusqlite::Result<Vec<String>> {
    let mut stmt = conn.prepare("SELECT target FROM edges WHERE source = ?")?;
    let rows = stmt.query_map(params![file_path], |row| row.get(0))?;
    rows.collect()
}

/// BFS trace: find a path from source to target through the call graph.
pub fn trace_path(
    conn: &Connection,
    source_fn: &str,
    source_file: &str,
    target_fn: &str,
    target_file: &str,
) -> rusqlite::Result<Vec<CallerInfo>> {
    use std::collections::{HashMap, HashSet, VecDeque};

    let mut visited: HashSet<(String, String)> = HashSet::new();
    let mut parent: HashMap<(String, String), (String, String, i64)> = HashMap::new();
    let mut queue: VecDeque<(String, String)> = VecDeque::new();

    let start = (source_fn.to_string(), source_file.to_string());
    let goal = (target_fn.to_string(), target_file.to_string());
    queue.push_back(start.clone());
    visited.insert(start.clone());

    let mut stmt = conn.prepare(
        "SELECT callee_function, callee_file, line FROM calls
         WHERE caller_function = ? AND caller_file = ?",
    )?;

    while let Some(current) = queue.pop_front() {
        if current == goal {
            // Reconstruct path
            let mut path = Vec::new();
            let mut node = current;
            while let Some((prev_fn, prev_file, line)) = parent.get(&node) {
                path.push(CallerInfo {
                    function: node.0.clone(),
                    file: node.1.clone(),
                    line: *line,
                });
                node = (prev_fn.clone(), prev_file.clone());
            }
            path.reverse();
            return Ok(path);
        }

        let callees: Vec<(String, String, i64)> = stmt
            .query_map(params![current.0, current.1], |row| {
                Ok((row.get(0)?, row.get(1)?, row.get(2)?))
            })?
            .collect::<Result<Vec<_>, _>>()?;

        for (callee_fn, callee_file, line) in callees {
            let next = (callee_fn, callee_file);
            if !visited.contains(&next) {
                visited.insert(next.clone());
                parent.insert(next.clone(), (current.0.clone(), current.1.clone(), line));
                queue.push_back(next);
            }
        }
    }

    Ok(Vec::new()) // no path found
}

/// Check if an entry exists in the content-addressed cache.
pub fn get_cached_entry(conn: &Connection, content_hash: &str) -> rusqlite::Result<bool> {
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM entry_cache WHERE content_hash = ?",
        params![content_hash],
        |row| row.get(0),
    )?;
    Ok(count > 0)
}

/// Get file stats.
pub fn file_count(conn: &Connection) -> rusqlite::Result<i64> {
    conn.query_row("SELECT COUNT(*) FROM files", [], |row| row.get(0))
}

pub fn symbol_count(conn: &Connection) -> rusqlite::Result<i64> {
    conn.query_row("SELECT COUNT(*) FROM symbols", [], |row| row.get(0))
}

pub fn edge_count(conn: &Connection) -> rusqlite::Result<i64> {
    conn.query_row("SELECT COUNT(*) FROM edges", [], |row| row.get(0))
}

pub fn call_count(conn: &Connection) -> rusqlite::Result<i64> {
    conn.query_row("SELECT COUNT(*) FROM calls", [], |row| row.get(0))
}
