"""Static Python symbol extraction using the standard-library AST only."""

from __future__ import annotations

import ast

from researchmind.models import CodeSymbol, CodeSymbolKind


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.symbols: list[CodeSymbol] = []
        self.scope: list[tuple[str, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._append_definition(node, kind="class")
        self.scope.append(("class", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._append_import(node, alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            name = f"{module}.{alias.name}" if module else alias.name
            self._append_import(node, name)

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        kind = (
            "method"
            if self.scope and self.scope[-1][0] == "class"
            else "function"
        )
        self._append_definition(node, kind=kind)
        self.scope.append(("function", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def _append_definition(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        *,
        kind: CodeSymbolKind,
    ) -> None:
        qualified_name = ".".join([*(name for _, name in self.scope), node.name])
        self.symbols.append(
            CodeSymbol(
                relative_path=self.relative_path,
                name=node.name,
                qualified_name=qualified_name,
                kind=kind,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                parent_name=self.scope[-1][1] if self.scope else None,
            )
        )

    def _append_import(self, node: ast.Import | ast.ImportFrom, name: str) -> None:
        self.symbols.append(
            CodeSymbol(
                relative_path=self.relative_path,
                name=name,
                qualified_name=name,
                kind="import",
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                parent_name=self.scope[-1][1] if self.scope else None,
            )
        )


def parse_python_symbols(
    relative_path: str,
    source: str,
) -> tuple[CodeSymbol, ...]:
    """Parse Python source without importing or executing it."""

    tree = ast.parse(source, filename=relative_path, mode="exec")
    visitor = _SymbolVisitor(relative_path)
    visitor.visit(tree)
    return tuple(
        sorted(
            visitor.symbols,
            key=lambda item: (
                item.start_line,
                item.end_line,
                item.qualified_name.casefold(),
            ),
        )
    )
