#!/usr/bin/env python3
"""
cavepeek.py — Caveman code introspector for Python 
v0.9.7 - Shebang fix edition | Kevin Joiner 2025

Outputs:
- Classes and methods
- Top-level functions (excluding main)
- main() as a distinct entry point
- Docstrings, return statements
- Conditional context for returns (with --verbose)
- Whether the file is executable
- Skips non-Python files gracefully
"""

import ast
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 🧠 AST Summary Walker
# ─────────────────────────────────────────────────────────────────────────────

class CodeSummary(ast.NodeVisitor):
    """Walks an AST and extracts high-level structure."""

    def __init__(self, source_lines):
        self.source_lines = source_lines
        self.module_doc = None
        self.top_level_funcs = []
        self.main_func = None
        self.classes = {}
        self.current_class = None
        self.has_main = False
        self.cond_stack = []

    def visit_Module(self, node):
        """Extract module-level docstring."""
        self.module_doc = ast.get_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        """Track class name and bucket its methods."""
        self.current_class = node.name
        self.classes[self.current_class] = []
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        """Handle function definition: capture name, args, docstring, returns."""
        func_info = {
            "name": node.name,
            "args": [arg.arg for arg in node.args.args],
            "doc": ast.get_docstring(node),
            "returns": []
        }
        self.visit_func_body(node.body, func_info)

        if self.current_class:
            self.classes[self.current_class].append(func_info)
        elif node.name == "main":
            self.main_func = func_info
        else:
            self.top_level_funcs.append(func_info)

    def visit_func_body(self, body, func_info):
        """Recursively walk a function body to track returns and conditions."""
        for stmt in body:
            if isinstance(stmt, ast.If):
                try:
                    cond = ast.unparse(stmt.test).strip()
                except Exception:
                    cond = "<unknown>"
                self.cond_stack.append(cond)
                self.visit_func_body(stmt.body, func_info)
                self.cond_stack.pop()

                if stmt.orelse:
                    self.cond_stack.append(f"not ({cond})")
                    self.visit_func_body(stmt.orelse, func_info)
                    self.cond_stack.pop()

            elif isinstance(stmt, ast.Return) and hasattr(stmt, 'lineno'):
                line = self.source_lines[stmt.lineno - 1].strip()
                func_info["returns"].append({
                    "line": line,
                    "conditions": list(self.cond_stack)
                })

            elif hasattr(stmt, 'body'):
                self.visit_func_body(getattr(stmt, 'body', []), func_info)

    def visit_If(self, node):
        """Check for if __name__ == '__main__' to mark as executable."""
        if (isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and
            node.test.left.id == '__name__'):
            self.has_main = True
        self.generic_visit(node)


# ─────────────────────────────────────────────────────────────────────────────
# 🖨 Pretty Printer Helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_func(func, indent=0, pad=True, verbose=False):
    """Format and print function metadata: name, args, docstring, returns."""
    """Print one function or method with its args, docstring, and return lines."""
    if pad:
        print()
    prefix = "  " * indent + f"\u2022 {func['name']}("
    args = ", ".join(func["args"])
    print(f"{prefix}{args})")
    if func["doc"]:
        print("  " * (indent + 1) + f"📘 {func['doc'].splitlines()[0]}")
    if func["returns"]:
        for ret in func["returns"]:
            if isinstance(ret, dict):
                conds = " | ".join(ret["conditions"])
                label = "✅" if "not" not in conds.lower() else "❌"
                line = ret["line"]
                if verbose and conds:
                    print("  " * (indent + 1) + f"↪ {line}  [when: {conds}] {label}")
                else:
                    print("  " * (indent + 1) + f"↪ {line}")
            else:
                print("  " * (indent + 1) + f"↪ {ret}")
    else:
        print("  " * (indent + 1) + "↪ (no return)")


# ─────────────────────────────────────────────────────────────────────────────
# 🚦 Main Summary Routine
# ─────────────────────────────────────────────────────────────────────────────

def summarize(filename, verbose=False):
    """Parse and print structural summary of a Python source file."""
    path = Path(filename)
    if not path.exists():
        print(f"❌ File not found: {filename}")
        sys.exit(1)

    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"❌ Failed to read file: {e}")
        sys.exit(1)

    # ── Shebang and file type check ──────────────────────────────────────────
    if not filename.endswith(".py") and not source.startswith("#!"):
        print(f"⚠️ Skipping: not a Python file or missing shebang")
        sys.exit(0)

    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"❌ SyntaxError: {e.msg} at line {e.lineno}, col {e.offset}")
        sys.exit(1)

    summary = CodeSummary(lines)
    summary.visit(tree)

    print(f"\n📄 {path.name}")
    print("─" * 30)

    if summary.module_doc:
        print("\n📘 Module:")
        for line in summary.module_doc.strip().splitlines():
            print(line)

    if summary.classes:
        print("\n🏩 Classes:")
        print("─" * 30)
        for cls, methods in summary.classes.items():
            print(f"\n🧱 class {cls}")
            for method in methods:
                print_func(method, indent=1, pad=False, verbose=verbose)

    if summary.top_level_funcs:
        print("\n🔧 Top-Level Functions:")
        print("─" * 30)
        for i, func in enumerate(summary.top_level_funcs):
            print_func(func, pad=(i > 0), verbose=verbose)

    if summary.main_func:
        print("\n🚀 Entry Point:")
        print("─" * 30)
        print_func(summary.main_func, pad=False, verbose=verbose)

    print("\n🚀 Executable:")
    print(f"{'Yes' if summary.has_main else 'No'} (has __main__ block)\n")


# ─────────────────────────────────────────────────────────────────────────────
# 🧃 Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Caveman code introspector for Python — shows structure, docstrings, return paths, and main block status."
    )
    parser.add_argument("filename", help="Python file to analyze")
    parser.add_argument("--verbose", action="store_true", help="Show conditions around return statements")
    args = parser.parse_args()

    summarize(args.filename, verbose=args.verbose)
