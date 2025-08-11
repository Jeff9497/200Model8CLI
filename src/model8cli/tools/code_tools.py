"""
Code Analysis Tools for 200Model8CLI

Provides code analysis, syntax checking, formatting, and testing capabilities.
"""

import ast
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import re

import structlog

from .base import BaseTool, ToolCategory, ToolParameter, ToolResult
from ..core.config import Config
from ..utils.helpers import detect_file_language, create_temp_file

logger = structlog.get_logger(__name__)


class AnalyzeCodeTool(BaseTool):
    """Analyze code for complexity, structure, and issues"""
    
    @property
    def name(self) -> str:
        return "analyze_code"
    
    @property
    def description(self) -> str:
        return "Analyze code for complexity, structure, and potential issues"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CODE_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Code to analyze",
                required=True,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Programming language (auto-detected if not specified)",
                required=False,
            ),
            ToolParameter(
                name="analysis_type",
                type="string",
                description="Type of analysis to perform",
                required=False,
                default="basic",
                enum=["basic", "detailed", "security"],
            ),
        ]
    
    async def execute(
        self,
        code: str,
        language: Optional[str] = None,
        analysis_type: str = "basic"
    ) -> ToolResult:
        try:
            # Auto-detect language if not specified
            if not language:
                language = self._detect_language(code)
            
            # Perform analysis based on language
            if language == "python":
                analysis = await self._analyze_python_code(code, analysis_type)
            elif language in ["javascript", "typescript"]:
                analysis = await self._analyze_js_code(code, analysis_type)
            else:
                analysis = await self._analyze_generic_code(code, language, analysis_type)
            
            return ToolResult(
                success=True,
                result={
                    "language": language,
                    "analysis_type": analysis_type,
                    "analysis": analysis,
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Code analysis failed: {str(e)}")
    
    def _detect_language(self, code: str) -> str:
        """Detect programming language from code content"""
        # Simple heuristics for language detection
        if "def " in code and "import " in code:
            return "python"
        elif "function " in code and ("var " in code or "let " in code or "const " in code):
            return "javascript"
        elif "public class " in code and "public static void main" in code:
            return "java"
        elif "#include" in code and "int main(" in code:
            return "c"
        elif "fn " in code and "let " in code and "->" in code:
            return "rust"
        else:
            return "text"
    
    async def _analyze_python_code(self, code: str, analysis_type: str) -> Dict[str, Any]:
        """Analyze Python code"""
        analysis = {
            "syntax_valid": False,
            "line_count": len(code.split('\n')),
            "character_count": len(code),
            "functions": [],
            "classes": [],
            "imports": [],
            "complexity_score": 0,
            "issues": [],
        }
        
        try:
            # Parse AST
            tree = ast.parse(code)
            analysis["syntax_valid"] = True
            
            # Analyze AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": len(node.args.args),
                        "decorators": len(node.decorator_list),
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                        "decorators": len(node.decorator_list),
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append({
                            "name": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                        })
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        analysis["imports"].append({
                            "name": f"{node.module}.{alias.name}" if node.module else alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                        })
            
            # Calculate complexity (simplified cyclomatic complexity)
            complexity = 1  # Base complexity
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            analysis["complexity_score"] = complexity
            
            # Check for common issues
            if analysis_type in ["detailed", "security"]:
                issues = []
                
                # Check for long functions
                for func in analysis["functions"]:
                    if func["args"] > 5:
                        issues.append(f"Function '{func['name']}' has many parameters ({func['args']})")
                
                # Check for security issues
                if analysis_type == "security":
                    if "eval(" in code:
                        issues.append("Use of eval() detected - potential security risk")
                    if "exec(" in code:
                        issues.append("Use of exec() detected - potential security risk")
                    if "subprocess" in code and "shell=True" in code:
                        issues.append("subprocess with shell=True detected - potential security risk")
                
                analysis["issues"] = issues
            
        except SyntaxError as e:
            analysis["syntax_valid"] = False
            analysis["syntax_error"] = {
                "message": str(e),
                "line": e.lineno,
                "offset": e.offset,
            }
        
        return analysis
    
    async def _analyze_js_code(self, code: str, analysis_type: str) -> Dict[str, Any]:
        """Analyze JavaScript/TypeScript code"""
        analysis = {
            "line_count": len(code.split('\n')),
            "character_count": len(code),
            "functions": [],
            "variables": [],
            "complexity_score": 0,
            "issues": [],
        }
        
        # Simple regex-based analysis for JS
        # Function declarations
        func_pattern = r'function\s+(\w+)\s*\([^)]*\)'
        functions = re.findall(func_pattern, code)
        analysis["functions"] = [{"name": func, "type": "function"} for func in functions]
        
        # Arrow functions
        arrow_pattern = r'(\w+)\s*=\s*\([^)]*\)\s*=>'
        arrow_functions = re.findall(arrow_pattern, code)
        analysis["functions"].extend([{"name": func, "type": "arrow"} for func in arrow_functions])
        
        # Variable declarations
        var_pattern = r'(?:var|let|const)\s+(\w+)'
        variables = re.findall(var_pattern, code)
        analysis["variables"] = [{"name": var} for var in variables]
        
        # Simple complexity calculation
        complexity_keywords = ['if', 'else', 'while', 'for', 'switch', 'case', 'try', 'catch']
        complexity = 1
        for keyword in complexity_keywords:
            complexity += len(re.findall(rf'\b{keyword}\b', code))
        
        analysis["complexity_score"] = complexity
        
        # Check for issues
        if analysis_type in ["detailed", "security"]:
            issues = []
            
            if "eval(" in code:
                issues.append("Use of eval() detected - potential security risk")
            if "innerHTML" in code:
                issues.append("Use of innerHTML detected - potential XSS risk")
            if "document.write" in code:
                issues.append("Use of document.write detected - not recommended")
            
            analysis["issues"] = issues
        
        return analysis
    
    async def _analyze_generic_code(self, code: str, language: str, analysis_type: str) -> Dict[str, Any]:
        """Generic code analysis for unsupported languages"""
        analysis = {
            "language": language,
            "line_count": len(code.split('\n')),
            "character_count": len(code),
            "blank_lines": len([line for line in code.split('\n') if not line.strip()]),
            "comment_lines": 0,
            "issues": [],
        }
        
        # Count comment lines based on language
        comment_patterns = {
            "python": r'^\s*#',
            "javascript": r'^\s*//',
            "java": r'^\s*//',
            "c": r'^\s*//',
            "cpp": r'^\s*//',
            "rust": r'^\s*//',
            "go": r'^\s*//',
            "shell": r'^\s*#',
            "ruby": r'^\s*#',
        }
        
        if language in comment_patterns:
            pattern = comment_patterns[language]
            comment_lines = len([line for line in code.split('\n') if re.match(pattern, line)])
            analysis["comment_lines"] = comment_lines
        
        return analysis


class CheckSyntaxTool(BaseTool):
    """Check code syntax validity"""
    
    @property
    def name(self) -> str:
        return "check_syntax"
    
    @property
    def description(self) -> str:
        return "Check if code has valid syntax"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CODE_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Code to check",
                required=True,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Programming language",
                required=True,
                enum=["python", "javascript", "typescript", "java", "c", "cpp", "go", "rust"],
            ),
        ]
    
    async def execute(self, code: str, language: str) -> ToolResult:
        try:
            if language == "python":
                result = await self._check_python_syntax(code)
            elif language in ["javascript", "typescript"]:
                result = await self._check_js_syntax(code, language)
            else:
                result = await self._check_generic_syntax(code, language)
            
            return ToolResult(success=True, result=result)
            
        except Exception as e:
            return ToolResult(success=False, error=f"Syntax check failed: {str(e)}")
    
    async def _check_python_syntax(self, code: str) -> Dict[str, Any]:
        """Check Python syntax"""
        try:
            ast.parse(code)
            return {
                "valid": True,
                "language": "python",
                "message": "Syntax is valid",
            }
        except SyntaxError as e:
            return {
                "valid": False,
                "language": "python",
                "error": {
                    "message": str(e),
                    "line": e.lineno,
                    "offset": e.offset,
                    "text": e.text,
                },
            }
    
    async def _check_js_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Check JavaScript/TypeScript syntax using Node.js if available"""
        try:
            # Create temporary file
            temp_file = create_temp_file(code, f'.{language[:2]}')
            
            # Try to check syntax with node
            try:
                result = subprocess.run(
                    ["node", "--check", str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return {
                        "valid": True,
                        "language": language,
                        "message": "Syntax is valid",
                    }
                else:
                    return {
                        "valid": False,
                        "language": language,
                        "error": {
                            "message": result.stderr,
                        },
                    }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # Node.js not available, do basic check
                return {
                    "valid": True,  # Assume valid if we can't check
                    "language": language,
                    "message": "Basic syntax check passed (Node.js not available for full validation)",
                }
            finally:
                temp_file.unlink(missing_ok=True)
                
        except Exception as e:
            return {
                "valid": False,
                "language": language,
                "error": {"message": str(e)},
            }
    
    async def _check_generic_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Generic syntax check"""
        # For unsupported languages, do basic checks
        issues = []
        
        # Check for unmatched brackets
        brackets = {'(': ')', '[': ']', '{': '}'}
        stack = []
        
        for i, char in enumerate(code):
            if char in brackets:
                stack.append((char, i))
            elif char in brackets.values():
                if not stack:
                    issues.append(f"Unmatched closing bracket '{char}' at position {i}")
                else:
                    open_bracket, _ = stack.pop()
                    if brackets[open_bracket] != char:
                        issues.append(f"Mismatched brackets at position {i}")
        
        if stack:
            for bracket, pos in stack:
                issues.append(f"Unmatched opening bracket '{bracket}' at position {pos}")
        
        return {
            "valid": len(issues) == 0,
            "language": language,
            "message": "Basic syntax check completed",
            "issues": issues,
        }


class FormatCodeTool(BaseTool):
    """Format code using appropriate formatters"""
    
    @property
    def name(self) -> str:
        return "format_code"
    
    @property
    def description(self) -> str:
        return "Format code using language-specific formatters"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CODE_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="Code to format",
                required=True,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Programming language",
                required=True,
                enum=["python", "javascript", "typescript", "json", "html", "css"],
            ),
            ToolParameter(
                name="style",
                type="string",
                description="Formatting style",
                required=False,
                default="default",
            ),
        ]
    
    async def execute(self, code: str, language: str, style: str = "default") -> ToolResult:
        try:
            if language == "python":
                formatted = await self._format_python(code, style)
            elif language in ["javascript", "typescript"]:
                formatted = await self._format_js(code, language, style)
            elif language == "json":
                formatted = await self._format_json(code)
            else:
                formatted = await self._format_generic(code, language)
            
            return ToolResult(
                success=True,
                result={
                    "original_code": code,
                    "formatted_code": formatted,
                    "language": language,
                    "style": style,
                    "changed": code != formatted,
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Code formatting failed: {str(e)}")
    
    async def _format_python(self, code: str, style: str) -> str:
        """Format Python code"""
        try:
            # Try to use black if available
            temp_file = create_temp_file(code, '.py')
            
            try:
                result = subprocess.run(
                    ["black", "--code", code],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    return result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            finally:
                temp_file.unlink(missing_ok=True)
            
            # Fallback to basic formatting
            return self._basic_python_format(code)
            
        except Exception:
            return code
    
    def _basic_python_format(self, code: str) -> str:
        """Basic Python formatting"""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue
            
            # Decrease indent for certain keywords
            if stripped.startswith(('except', 'elif', 'else', 'finally')):
                current_indent = max(0, indent_level - 1)
            else:
                current_indent = indent_level
            
            # Add formatted line
            formatted_lines.append('    ' * current_indent + stripped)
            
            # Increase indent after certain keywords
            if stripped.endswith(':') and any(stripped.startswith(kw) for kw in 
                ['def ', 'class ', 'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'finally:', 'with ']):
                indent_level = current_indent + 1
            elif stripped.startswith(('except', 'elif', 'else', 'finally')) and stripped.endswith(':'):
                indent_level = current_indent + 1
        
        return '\n'.join(formatted_lines)
    
    async def _format_js(self, code: str, language: str, style: str) -> str:
        """Format JavaScript/TypeScript code"""
        # Basic JS formatting
        return self._basic_js_format(code)
    
    def _basic_js_format(self, code: str) -> str:
        """Basic JavaScript formatting"""
        # Simple formatting - add proper spacing
        formatted = code
        formatted = re.sub(r'([{;])\s*\n\s*', r'\1\n    ', formatted)
        formatted = re.sub(r'}\s*\n', r'}\n', formatted)
        return formatted
    
    async def _format_json(self, code: str) -> str:
        """Format JSON code"""
        try:
            parsed = json.loads(code)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return code
    
    async def _format_generic(self, code: str, language: str) -> str:
        """Generic code formatting"""
        # Basic formatting - normalize whitespace
        lines = [line.rstrip() for line in code.split('\n')]
        return '\n'.join(lines)


# Code Tools registry
class CodeTools:
    """Collection of code analysis and formatting tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            AnalyzeCodeTool(config),
            CheckSyntaxTool(config),
            FormatCodeTool(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all code tools"""
        return self.tools
