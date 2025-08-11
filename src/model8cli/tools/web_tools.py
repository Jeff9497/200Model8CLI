"""
Web & Search Tools for 200Model8CLI

Provides web search, page fetching, and code extraction capabilities using free methods.
"""

import asyncio
import re
import json
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse, quote_plus
import time

import httpx
import structlog
from bs4 import BeautifulSoup

from .base import BaseTool, ToolCategory, ToolParameter, ToolResult
from ..core.config import Config
from ..utils.helpers import truncate_text

logger = structlog.get_logger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo (no API required)"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web for information using DuckDuckGo"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Search query",
                required=True,
                max_length=500,
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of results (default: 5)",
                required=False,
                default=5,
                min_value=1,
                max_value=20,
            ),
            ToolParameter(
                name="region",
                type="string",
                description="Search region (us-en, uk-en, etc.)",
                required=False,
                default="us-en",
            ),
        ]
    
    async def execute(
        self,
        query: str,
        max_results: int = 5,
        region: str = "us-en"
    ) -> ToolResult:
        try:
            # Validate query
            if not query.strip():
                return ToolResult(success=False, error="Query cannot be empty")
            
            # Perform search
            results = await self._search_duckduckgo(query, max_results, region)
            
            if not results:
                return ToolResult(
                    success=True,
                    result={
                        "query": query,
                        "results": [],
                        "total_found": 0,
                        "message": "No results found"
                    }
                )
            
            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "results": results,
                    "total_found": len(results),
                    "region": region,
                }
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {str(e)}")
    
    async def _search_duckduckgo(
        self, 
        query: str, 
        max_results: int, 
        region: str
    ) -> List[Dict[str, Any]]:
        """Search DuckDuckGo using their HTML interface"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            # URL encode the query
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}&kl={region}"
            
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                
                # Find search result containers
                result_containers = soup.find_all('div', class_='result')
                
                for container in result_containers[:max_results]:
                    try:
                        # Extract title and link
                        title_elem = container.find('a', class_='result__a')
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get('href', '')
                        
                        # Extract snippet
                        snippet_elem = container.find('a', class_='result__snippet')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        # Clean up the link (DuckDuckGo sometimes wraps URLs)
                        if link.startswith('/l/?uddg='):
                            # Extract actual URL from DuckDuckGo redirect
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                            if 'uddg' in parsed:
                                link = urllib.parse.unquote(parsed['uddg'][0])
                        
                        if title and link:
                            results.append({
                                "title": title,
                                "url": link,
                                "snippet": snippet,
                                "source": "DuckDuckGo"
                            })
                    
                    except Exception as e:
                        logger.warning("Failed to parse search result", error=str(e))
                        continue
                
                return results
                
        except Exception as e:
            logger.error("DuckDuckGo search failed", error=str(e))
            raise


class WebFetchTool(BaseTool):
    """Fetch content from web pages"""
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch and extract content from web pages"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="URL to fetch",
                required=True,
            ),
            ToolParameter(
                name="extract_text",
                type="boolean",
                description="Extract main text content (default: true)",
                required=False,
                default=True,
            ),
            ToolParameter(
                name="extract_links",
                type="boolean",
                description="Extract links from the page (default: false)",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="max_content_length",
                type="integer",
                description="Maximum content length in characters (default: 50000)",
                required=False,
                default=50000,
                min_value=1000,
                max_value=200000,
            ),
        ]
    
    async def execute(
        self,
        url: str,
        extract_text: bool = True,
        extract_links: bool = False,
        max_content_length: int = 50000
    ) -> ToolResult:
        try:
            # Validate URL
            if not self.security.validate_url(url):
                return ToolResult(success=False, error="URL validation failed")
            
            # Fetch page
            content_data = await self._fetch_page(url, extract_text, extract_links, max_content_length)
            
            return ToolResult(
                success=True,
                result=content_data
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to fetch page: {str(e)}")
    
    async def _fetch_page(
        self,
        url: str,
        extract_text: bool,
        extract_links: bool,
        max_content_length: int
    ) -> Dict[str, Any]:
        """Fetch and parse web page"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""
            
            result = {
                "url": str(response.url),
                "title": title_text,
                "status_code": response.status_code,
                "content_type": response.headers.get('content-type', ''),
            }
            
            # Extract main text content
            if extract_text:
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Get text content
                text_content = soup.get_text()
                
                # Clean up text
                lines = (line.strip() for line in text_content.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text_content = ' '.join(chunk for chunk in chunks if chunk)
                
                # Truncate if too long
                if len(text_content) > max_content_length:
                    text_content = text_content[:max_content_length] + "... [truncated]"
                
                result["text_content"] = text_content
                result["content_length"] = len(text_content)
            
            # Extract links
            if extract_links:
                links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    link_text = link.get_text(strip=True)
                    
                    # Convert relative URLs to absolute
                    if href.startswith('/'):
                        href = urljoin(url, href)
                    elif not href.startswith(('http://', 'https://')):
                        continue
                    
                    if link_text and href:
                        links.append({
                            "text": link_text,
                            "url": href
                        })
                
                result["links"] = links[:50]  # Limit to 50 links
            
            return result


class ExtractCodeTool(BaseTool):
    """Extract code from GitHub/GitLab URLs"""
    
    @property
    def name(self) -> str:
        return "extract_code"
    
    @property
    def description(self) -> str:
        return "Extract code content from GitHub, GitLab, or other code hosting URLs"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_TOOLS
    
    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="URL to code file or repository",
                required=True,
            ),
            ToolParameter(
                name="raw_content",
                type="boolean",
                description="Get raw content instead of HTML (default: true)",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        url: str,
        raw_content: bool = True
    ) -> ToolResult:
        try:
            # Validate URL
            if not self.security.validate_url(url):
                return ToolResult(success=False, error="URL validation failed")
            
            # Convert to raw URL if needed
            raw_url = self._convert_to_raw_url(url) if raw_content else url
            
            # Fetch code content
            code_data = await self._fetch_code(raw_url, url)
            
            return ToolResult(
                success=True,
                result=code_data
            )
            
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to extract code: {str(e)}")
    
    def _convert_to_raw_url(self, url: str) -> str:
        """Convert GitHub/GitLab URLs to raw content URLs"""
        # GitHub
        if 'github.com' in url and '/blob/' in url:
            return url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
        
        # GitLab
        if 'gitlab.com' in url and '/blob/' in url:
            return url.replace('/blob/', '/raw/')
        
        # Bitbucket
        if 'bitbucket.org' in url and '/src/' in url:
            return url.replace('/src/', '/raw/')
        
        return url
    
    async def _fetch_code(self, raw_url: str, original_url: str) -> Dict[str, Any]:
        """Fetch code content"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/plain,text/html,application/xhtml+xml,*/*;q=0.8',
        }
        
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            response = await client.get(raw_url, follow_redirects=True)
            response.raise_for_status()
            
            content = response.text
            
            # Detect file type from URL
            file_extension = self._get_file_extension(original_url)
            language = self._detect_language_from_extension(file_extension)
            
            # Extract filename
            filename = original_url.split('/')[-1] if '/' in original_url else 'code'
            
            return {
                "url": original_url,
                "raw_url": raw_url,
                "filename": filename,
                "file_extension": file_extension,
                "language": language,
                "content": content,
                "content_length": len(content),
                "line_count": content.count('\n') + 1 if content else 0,
            }
    
    def _get_file_extension(self, url: str) -> str:
        """Extract file extension from URL"""
        path = urlparse(url).path
        if '.' in path:
            return path.split('.')[-1].lower()
        return ""
    
    def _detect_language_from_extension(self, extension: str) -> str:
        """Detect programming language from file extension"""
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'jsx': 'jsx',
            'tsx': 'tsx',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'h': 'c',
            'cs': 'csharp',
            'go': 'go',
            'rs': 'rust',
            'php': 'php',
            'rb': 'ruby',
            'swift': 'swift',
            'kt': 'kotlin',
            'scala': 'scala',
            'clj': 'clojure',
            'hs': 'haskell',
            'ml': 'ocaml',
            'r': 'r',
            'sql': 'sql',
            'html': 'html',
            'css': 'css',
            'scss': 'scss',
            'less': 'less',
            'vue': 'vue',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'toml': 'toml',
            'md': 'markdown',
            'sh': 'bash',
            'bat': 'batch',
            'ps1': 'powershell',
        }
        
        return language_map.get(extension, 'text')


# Web Tools registry
class WebTools:
    """Collection of web and search tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = [
            WebSearchTool(config),
            WebFetchTool(config),
            ExtractCodeTool(config),
        ]
    
    def get_tools(self) -> List[BaseTool]:
        """Get all web tools"""
        return self.tools
