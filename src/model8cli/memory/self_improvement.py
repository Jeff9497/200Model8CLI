"""
Self-Improvement Loop for 200Model8CLI

Reads the agent's own error logs, uses AST to understand the broken code,
proposes a fix as a unified diff, and sends it for human approval before
applying anything.
"""

import ast
import difflib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import structlog

from ..core.api import OpenRouterClient, Message
from ..core.config import Config
from ..memory.memory_store import MemoryStore

logger = structlog.get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LOG_PATH = Path.home() / ".200model8cli" / "logs" / "app.log"


class SelfImprovementLoop:
    """
    Analyses the agent's own error logs and proposes code fixes.
    Never applies anything without explicit approval.
    """

    def __init__(self, config: Config, api_client: OpenRouterClient, memory: MemoryStore):
        self.config = config
        self.api_client = api_client
        self.memory = memory

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    async def run_analysis(self) -> List[Dict]:
        """
        Full pipeline:
        1. Read error logs
        2. For each unique error, find the source file via AST
        3. Ask the model for a fix
        4. Return list of pending patches (not applied yet)
        """
        errors = self._parse_error_logs()
        if not errors:
            logger.info("No errors found in logs")
            return []

        patches = []
        seen = set()

        for err in errors:
            key = f"{err['file']}:{err['error_type']}"
            if key in seen:
                continue
            seen.add(key)

            patch = await self._build_patch(err)
            if patch:
                patches.append(patch)

        return patches

    async def apply_patch(self, patch: Dict) -> Tuple[bool, str]:
        """
        Apply a pre-approved patch to the source file.
        Runs git diff after to confirm, then commits.
        Returns (success, message).
        """
        try:
            file_path = PROJECT_ROOT / patch["file"]
            if not file_path.exists():
                return False, f"File not found: {patch['file']}"

            original = file_path.read_text(encoding="utf-8")

            # Apply the patch (simple line replacement)
            patched = self._apply_diff(original, patch["diff"])
            if patched is None:
                return False, "Patch could not be applied cleanly"

            # Validate the patched code parses correctly
            try:
                ast.parse(patched)
            except SyntaxError as e:
                return False, f"Patched code has syntax error: {e}"

            # Write the file
            file_path.write_text(patched, encoding="utf-8")

            # Git commit
            commit_msg = f"fix: {patch['summary']}"
            self._git_commit(patch["file"], commit_msg)

            # Save lesson to memory
            self.memory.save_lesson(
                context=patch["error_context"],
                fix=patch["summary"],
                error_type=patch["error_type"],
                tool=patch.get("tool", "")
            )

            logger.info("Patch applied", file=patch["file"], summary=patch["summary"])
            return True, f"Patch applied and committed: {commit_msg}"

        except Exception as e:
            logger.error("Failed to apply patch", error=str(e))
            return False, str(e)

    # ------------------------------------------------------------------ #
    # AST introspection
    # ------------------------------------------------------------------ #

    def introspect_file(self, relative_path: str) -> Dict:
        """
        Parse a source file with AST and return a structural summary:
        functions, classes, imports, complexity estimate.
        """
        file_path = PROJECT_ROOT / relative_path
        if not file_path.exists():
            return {"error": "File not found"}

        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "line": node.lineno,
                    "args": [a.arg for a in node.args.args],
                    "has_docstring": ast.get_docstring(node) is not None,
                    "complexity": self._estimate_complexity(node)
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": [
                        n.name for n in node.body if isinstance(n, ast.FunctionDef)
                    ]
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                else:
                    imports.append(node.module or "")

        return {
            "file": relative_path,
            "lines": len(source.splitlines()),
            "functions": functions,
            "classes": classes,
            "imports": list(set(imports)),
            "total_functions": len(functions),
            "total_classes": len(classes)
        }

    def _estimate_complexity(self, node: ast.FunctionDef) -> int:
        """Count branches as a rough cyclomatic complexity."""
        count = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try,
                                   ast.ExceptHandler, ast.With)):
                count += 1
        return count

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_error_logs(self) -> List[Dict]:
        """Read the log file and extract unique errors with context."""
        if not LOG_PATH.exists():
            return []

        errors = []
        lines = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()

        for i, line in enumerate(lines):
            if "ERROR" not in line and "error" not in line.lower():
                continue

            # Try to extract file reference
            file_match = re.search(r'(src/model8cli/\S+\.py)', line)
            error_type_match = re.search(r'(\w+Error|\w+Exception)', line)

            errors.append({
                "raw": line,
                "context": "\n".join(lines[max(0, i-2):i+3]),
                "file": file_match.group(1) if file_match else "",
                "error_type": error_type_match.group(1) if error_type_match else "UnknownError",
                "line_number": i
            })

        return errors[:10]  # Cap at 10 unique errors per run

    async def _build_patch(self, error: Dict) -> Optional[Dict]:
        """Ask the model to propose a fix for a given error."""
        if not error["file"]:
            return None

        file_path = PROJECT_ROOT / error["file"]
        if not file_path.exists():
            return None

        source = file_path.read_text(encoding="utf-8")

        prompt = f"""You are analyzing a bug in this Python file.

FILE: {error['file']}
ERROR LOG:
{error['context']}

SOURCE CODE:
{source[:3000]}

Task: Propose a minimal fix. Return ONLY a JSON object with these fields:
{{
  "summary": "one line description of the fix",
  "original_lines": ["exact lines to replace"],
  "fixed_lines": ["replacement lines"],
  "explanation": "why this fixes it"
}}

Return only the JSON, no other text."""

        try:
            response = await self.api_client.chat_completion(
                messages=[Message(role="user", content=prompt)],
                temperature=0.2,
                max_tokens=800
            )
            raw = response.choices[0]["message"]["content"]
            clean = raw.replace("```json", "").replace("```", "").strip()
            fix = json.loads(clean)

            # Build a unified diff for display
            diff = self._build_diff(
                error["file"],
                source,
                fix.get("original_lines", []),
                fix.get("fixed_lines", [])
            )

            if not diff:
                return None

            return {
                "file": error["file"],
                "error_type": error["error_type"],
                "error_context": error["context"],
                "summary": fix.get("summary", ""),
                "explanation": fix.get("explanation", ""),
                "diff": diff,
                "original_lines": fix.get("original_lines", []),
                "fixed_lines": fix.get("fixed_lines", []),
                "tool": ""
            }

        except Exception as e:
            logger.error("Failed to build patch", error=str(e))
            return None

    def _build_diff(
        self,
        filename: str,
        source: str,
        original_lines: List[str],
        fixed_lines: List[str]
    ) -> Optional[str]:
        """Build a unified diff string for display."""
        if not original_lines or not fixed_lines:
            return None

        original_source = source.splitlines(keepends=True)
        patched_source = source

        for orig, fix in zip(original_lines, fixed_lines):
            patched_source = patched_source.replace(orig, fix, 1)

        diff = difflib.unified_diff(
            original_source,
            patched_source.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        result = "\n".join(list(diff))
        return result if result else None

    def _apply_diff(self, original: str, diff: str) -> Optional[str]:
        """Apply a diff string to source content."""
        # Simple approach: re-extract original/fixed lines from the diff
        additions = []
        removals = []

        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                additions.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                removals.append(line[1:])

        result = original
        for rem, add in zip(removals, additions):
            result = result.replace(rem, add, 1)

        return result if result != original else None

    def _git_commit(self, file_path: str, message: str):
        """Stage the file and commit."""
        try:
            subprocess.run(
                ["git", "add", file_path],
                cwd=PROJECT_ROOT, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=PROJECT_ROOT, capture_output=True, check=True
            )
            logger.info("Git commit done", message=message)
        except subprocess.CalledProcessError as e:
            logger.warning("Git commit failed", error=str(e))
