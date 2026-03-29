"""Infrastructure: multi-language import parser.

Implements ImportParser port. Layered strategy:
  tree-sitter -> ast-grep -> Python ast -> regex
"""

from __future__ import annotations

from src.domain.import_ref import ImportRef
from src.domain.ports.import_parser import ImportParser

# Re-use the existing comprehensive parser module
from lang_parsers import (
    parse_imports as _raw_parse_imports,
    parse_symbols as _raw_parse_symbols,
)
from src.domain.symbol_def import SymbolDef
from src.domain.ports.symbol_extractor import SymbolExtractor


class MultiLangImportParser(ImportParser):
    """Parses imports across 15+ languages."""

    def parse(self, file_path: str, source: str) -> list[ImportRef]:
        raw = _raw_parse_imports(file_path, source)
        return [ImportRef(raw=r.raw, module=r.module, kind=r.kind) for r in raw]


class MultiLangSymbolExtractor(SymbolExtractor):
    """Extracts symbols across multiple languages."""

    def extract(self, file_path: str, source: str) -> list[SymbolDef]:
        raw = _raw_parse_symbols(file_path, source)
        return [
            SymbolDef(name=s.name, kind=s.kind, line=s.line, scope=s.scope)
            for s in raw
        ]
