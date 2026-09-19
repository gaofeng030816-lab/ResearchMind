"""Tree-sitter adapters for C, Java, and Julia static reading."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from tree_sitter import Language, Node, Parser
import tree_sitter_c
import tree_sitter_java
import tree_sitter_julia

from researchmind.models import CodeLanguage, CodeSymbol, CodeSymbolKind


_TREE_SITTER_LANGUAGES = frozenset({"c", "java", "julia"})


@lru_cache(maxsize=3)
def _parser(language: CodeLanguage) -> Parser:
    if language not in _TREE_SITTER_LANGUAGES:
        raise ValueError(f"Tree-sitter is not configured for {language}.")
    factories: dict[str, Any] = {
        "c": tree_sitter_c.language,
        "java": tree_sitter_java.language,
        "julia": tree_sitter_julia.language,
    }
    return Parser(Language(factories[language]()))


def parse_tree_sitter_symbols(
    language: CodeLanguage,
    relative_path: str,
    source: str,
) -> tuple[CodeSymbol, ...]:
    """Parse supported source and map vendor nodes into project-owned symbols."""

    source_bytes = source.encode("utf-8")
    tree = _parser(language).parse(source_bytes)
    if tree.root_node.has_error:
        error = _first_error(tree.root_node)
        exc = SyntaxError(f"{language} parser reported an incomplete syntax tree")
        exc.lineno = (error.start_point.row + 1) if error is not None else 1
        raise exc

    symbols: list[CodeSymbol] = []
    if language == "c":
        _collect_c(tree.root_node, source_bytes, relative_path, symbols)
    elif language == "java":
        _collect_java(tree.root_node, source_bytes, relative_path, symbols, None)
    else:
        _collect_julia(tree.root_node, source_bytes, relative_path, symbols)
    return _deduplicated(symbols)


def _collect_c(
    node: Node,
    source: bytes,
    relative_path: str,
    symbols: list[CodeSymbol],
) -> None:
    if node.type == "preproc_include":
        name = _node_text(node, source).removeprefix("#include").strip()
        _append(symbols, node, relative_path, name, name, "import")
    elif node.type == "function_definition":
        declarator = node.child_by_field_name("declarator")
        name = _declarator_name(declarator, source)
        if name:
            _append(symbols, node, relative_path, name, name, "function")
    elif node.type == "type_definition":
        declarator = node.child_by_field_name("declarator")
        name = _declarator_name(declarator, source)
        if name:
            _append(symbols, node, relative_path, name, name, "type")
    elif node.type in {"struct_specifier", "union_specifier", "enum_specifier"}:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            name = _node_text(name_node, source)
            _append(symbols, node, relative_path, name, name, "type")
    for child in node.named_children:
        _collect_c(child, source, relative_path, symbols)


def _collect_java(
    node: Node,
    source: bytes,
    relative_path: str,
    symbols: list[CodeSymbol],
    parent_type: str | None,
) -> None:
    type_nodes = {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "annotation_type_declaration",
    }
    current_parent = parent_type
    if node.type == "import_declaration":
        name = _node_text(node, source).removeprefix("import").removesuffix(";").strip()
        name = name.removeprefix("static").strip()
        _append(symbols, node, relative_path, name, name, "import")
    elif node.type in type_nodes:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            name = _node_text(name_node, source)
            qualified = f"{parent_type}.{name}" if parent_type else name
            _append(symbols, node, relative_path, name, qualified, "type", parent_type)
            current_parent = qualified
    elif node.type in {"method_declaration", "constructor_declaration"}:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            name = _node_text(name_node, source)
            qualified = f"{parent_type}.{name}" if parent_type else name
            _append(
                symbols,
                node,
                relative_path,
                name,
                qualified,
                "method",
                parent_type,
            )
    for child in node.named_children:
        _collect_java(child, source, relative_path, symbols, current_parent)


def _collect_julia(
    node: Node,
    source: bytes,
    relative_path: str,
    symbols: list[CodeSymbol],
) -> None:
    if node.type in {"using_statement", "import_statement"}:
        text = _node_text(node, source)
        name = text.split(maxsplit=1)[1].strip() if " " in text else text
        _append(symbols, node, relative_path, name, name, "import")
    elif node.type == "function_definition":
        name = _julia_function_name(node, source)
        if name:
            _append(symbols, node, relative_path, name, name, "function")
    elif node.type in {
        "struct_definition",
        "abstract_definition",
        "primitive_definition",
    }:
        name_node = node.child_by_field_name("name") or node
        name = _declarator_name(name_node, source)
        if name:
            _append(symbols, node, relative_path, name, name, "type")
    for child in node.named_children:
        _collect_julia(child, source, relative_path, symbols)


def _julia_function_name(node: Node, source: bytes) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _node_text(name_node, source)
    signature = next(
        (
            child
            for child in node.named_children
            if child.type in {"call_expression", "signature"}
        ),
        None,
    )
    if signature is None:
        return ""
    text = _node_text(signature, source)
    return text.split("(", maxsplit=1)[0].strip()


def _declarator_name(node: Node | None, source: bytes) -> str:
    if node is None:
        return ""
    if node.type in {"identifier", "type_identifier", "field_identifier"}:
        return _node_text(node, source)
    for child in node.named_children:
        name = _declarator_name(child, source)
        if name:
            return name
    return ""


def _append(
    symbols: list[CodeSymbol],
    node: Node,
    relative_path: str,
    name: str,
    qualified_name: str,
    kind: CodeSymbolKind,
    parent_name: str | None = None,
) -> None:
    end_line = node.end_point.row + (1 if node.end_point.column else 0)
    symbols.append(
        CodeSymbol(
            relative_path=relative_path,
            name=name,
            qualified_name=qualified_name,
            kind=kind,
            start_line=node.start_point.row + 1,
            end_line=max(node.start_point.row + 1, end_line),
            parent_name=parent_name,
        )
    )


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _first_error(node: Node) -> Node | None:
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        found = _first_error(child)
        if found is not None:
            return found
    return None


def _deduplicated(symbols: list[CodeSymbol]) -> tuple[CodeSymbol, ...]:
    unique = {
        (
            item.kind,
            item.qualified_name,
            item.start_line,
            item.end_line,
        ): item
        for item in symbols
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.start_line,
                item.end_line,
                item.kind,
                item.qualified_name,
            ),
        )
    )
