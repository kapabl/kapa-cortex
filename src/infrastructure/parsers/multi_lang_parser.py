"""Infrastructure: multi-language import and symbol parser.

Implements ImportParser and SymbolExtractor ports.
Delegates to the import_dispatcher for imports and
tree-sitter/ctags for symbol extraction.
"""

from __future__ import annotations

from src.domain.entity.import_ref import ImportRef
from src.domain.entity.symbol_def import SymbolDef
from src.domain.port.import_parser import ImportParser
from src.domain.port.symbol_extractor import SymbolExtractor
from src.infrastructure.parsers.import_dispatcher import dispatch_parse_imports
from src.infrastructure.parsers.language_detector import detect_language
from src.infrastructure.parsers import tree_sitter_parser as ts
from src.infrastructure.parsers import ctags_parser


class MultiLangImportParser(ImportParser):
    """Parses imports across 15+ languages."""

    def parse(self, file_path: str, source: str) -> list[ImportRef]:
        return dispatch_parse_imports(file_path, source)


class MultiLangSymbolExtractor(SymbolExtractor):
    """Extracts symbol definitions via tree-sitter, falls back to ctags."""

    def extract(self, file_path: str, source: str) -> list[SymbolDef]:
        lang = detect_language(file_path)
        if not lang:
            return []

        # Layer 1: tree-sitter
        results = ts.extract_symbols(source, lang)
        if results:
            return results

        # Layer 2: ctags
        return ctags_parser.extract_symbols(file_path, source)
