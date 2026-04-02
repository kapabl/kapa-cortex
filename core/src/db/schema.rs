use rusqlite::Connection;

pub fn create_tables(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS files (
            path         TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            language     TEXT,
            lines        INTEGER,
            complexity   INTEGER
        );

        CREATE TABLE IF NOT EXISTS symbols (
            file_path TEXT NOT NULL,
            name      TEXT NOT NULL,
            kind      TEXT,
            line      INTEGER,
            scope     TEXT
        );

        CREATE TABLE IF NOT EXISTS imports (
            file_path TEXT NOT NULL,
            raw       TEXT,
            module    TEXT,
            kind      TEXT
        );

        CREATE TABLE IF NOT EXISTS edges (
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            kind   TEXT NOT NULL,
            PRIMARY KEY (source, target, kind)
        );

        CREATE TABLE IF NOT EXISTS calls (
            caller_file     TEXT NOT NULL,
            caller_function TEXT NOT NULL,
            callee_file     TEXT NOT NULL,
            callee_function TEXT NOT NULL,
            line            INTEGER
        );

        CREATE TABLE IF NOT EXISTS entry_cache (
            content_hash TEXT PRIMARY KEY,
            symbols      BLOB,
            imports      BLOB,
            calls        BLOB
        );

        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
        CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
        CREATE INDEX IF NOT EXISTS idx_symbols_scope ON symbols(scope);
        CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_function, callee_file);
        CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_function, caller_file);
        CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
        CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
        ",
    )
}
