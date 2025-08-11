"""
Browser automation tools for web interaction
"""
import asyncio
import webbrowser
import subprocess
import platform
from typing import List, Optional, Dict, Any
from pathlib import Path

from model8cli.tools.base import BaseTool, ToolResult, ToolParameter, ToolCategory
from model8cli.utils.logging import get_logger

logger = get_logger(__name__)


class OpenBrowserTool(BaseTool):
    """Tool to open URLs in browser"""

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return "Open a URL in the default browser or specified browser"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WEB_TOOLS

    def get_parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                type="string",
                description="URL to open",
                required=True,
            ),
            ToolParameter(
                name="browser",
                type="string",
                description="Browser to use (chrome, firefox, edge, brave, default)",
                required=False,
                default="default",
                enum=["chrome", "firefox", "edge", "brave", "default"]
            ),
            ToolParameter(
                name="new_tab",
                type="boolean",
                description="Open in new tab",
                required=False,
                default=True,
            ),
        ]
    
    async def execute(
        self,
        url: str,
        browser: str = "default",
        new_tab: bool = True
    ) -> ToolResult:
        """Open URL in browser"""
        try:
            # Validate URL
            if not url.startswith(('http://', 'https://')):
                url = f"https://{url}"
            
            if browser == "default":
                # Use default browser
                if new_tab:
                    webbrowser.open_new_tab(url)
                else:
                    webbrowser.open(url)
            else:
                # Use specific browser
                success = await self._open_with_specific_browser(url, browser, new_tab)
                if not success:
                    # Fallback to default browser
                    webbrowser.open_new_tab(url)
            
            return ToolResult(
                success=True,
                result={
                    "url": url,
                    "browser": browser,
                    "opened": True,
                    "message": f"Opened {url} in {browser} browser"
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to open browser: {str(e)}"
            )
    
    async def _open_with_specific_browser(self, url: str, browser: str, new_tab: bool) -> bool:
        """Open URL with specific browser"""
        try:
            system = platform.system().lower()
            
            if system == "windows":
                browser_paths = {
                    "chrome": [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                    ],
                    "firefox": [
                        r"C:\Program Files\Mozilla Firefox\firefox.exe",
                        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
                    ],
                    "edge": [
                        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                    ],
                    "brave": [
                        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"
                    ]
                }
            elif system == "darwin":  # macOS
                browser_paths = {
                    "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
                    "firefox": ["/Applications/Firefox.app/Contents/MacOS/firefox"],
                    "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
                    "brave": ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]
                }
            else:  # Linux
                browser_paths = {
                    "chrome": ["google-chrome", "chromium-browser"],
                    "firefox": ["firefox"],
                    "edge": ["microsoft-edge"],
                    "brave": ["brave-browser"]
                }
            
            if browser not in browser_paths:
                return False
            
            # Try each path for the browser
            for browser_path in browser_paths[browser]:
                if system == "windows" or system == "darwin":
                    if Path(browser_path).exists():
                        args = [browser_path]
                        if new_tab:
                            args.append("--new-tab")
                        args.append(url)
                        subprocess.Popen(args)
                        return True
                else:  # Linux
                    try:
                        args = [browser_path]
                        if new_tab:
                            args.append("--new-tab")
                        args.append(url)
                        subprocess.Popen(args)
                        return True
                    except FileNotFoundError:
                        continue
            
            return False
            
        except Exception as e:
            logger.error("Failed to open specific browser", browser=browser, error=str(e))
            return False


class SearchBrowserTool(BaseTool):
    """Tool to search directly in browser"""

    @property
    def name(self) -> str:
        return "search_browser"

    @property
    def description(self) -> str:
        return "Search for something directly in browser using search engine"

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
            ),
            ToolParameter(
                name="search_engine",
                type="string",
                description="Search engine to use",
                required=False,
                default="google",
                enum=["google", "bing", "duckduckgo", "brave"]
            ),
            ToolParameter(
                name="browser",
                type="string",
                description="Browser to use",
                required=False,
                default="default",
                enum=["chrome", "firefox", "edge", "brave", "default"]
            ),
        ]
    
    async def execute(
        self,
        query: str,
        search_engine: str = "google",
        browser: str = "default"
    ) -> ToolResult:
        """Search in browser"""
        try:
            # Build search URL
            search_urls = {
                "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
                "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
                "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                "brave": f"https://search.brave.com/search?q={query.replace(' ', '+')}"
            }
            
            search_url = search_urls.get(search_engine, search_urls["google"])
            
            # Open search in browser
            open_tool = OpenBrowserTool(self.config)
            result = await open_tool.execute(search_url, browser, True)

            if result.success:
                # Also fetch the web content to provide insights
                try:
                    from .web_tools import WebFetchTool
                    web_fetch = WebFetchTool(self.config)
                    fetch_result = await web_fetch.execute(search_url, extract_main_content=True)

                    web_content = ""
                    if fetch_result.success:
                        content_data = fetch_result.result
                        web_content = content_data.get('main_content', '')[:1000]  # First 1000 chars

                    return ToolResult(
                        success=True,
                        result={
                            "query": query,
                            "search_engine": search_engine,
                            "browser": browser,
                            "search_url": search_url,
                            "web_content_preview": web_content,
                            "message": f"Opened search for '{query}' in {search_engine} using {browser} browser and fetched content preview"
                        }
                    )
                except Exception as e:
                    # Fallback to basic result if web fetch fails
                    return ToolResult(
                        success=True,
                        result={
                            "query": query,
                            "search_engine": search_engine,
                            "browser": browser,
                            "search_url": search_url,
                            "message": f"Opened search for '{query}' in {search_engine} using {browser} browser"
                        }
                    )
            else:
                return result
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to search in browser: {str(e)}"
            )


class SearchAndAnalyzeTool(BaseTool):
    """Tool to search in browser and analyze the results"""

    @property
    def name(self) -> str:
        return "search_and_analyze"

    @property
    def description(self) -> str:
        return "Search for something in browser and analyze the results to provide insights"

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
            ),
            ToolParameter(
                name="search_engine",
                type="string",
                description="Search engine to use",
                required=False,
                default="google",
                enum=["google", "bing", "duckduckgo", "brave"]
            ),
            ToolParameter(
                name="browser",
                type="string",
                description="Browser to use",
                required=False,
                default="default",
                enum=["chrome", "firefox", "edge", "brave", "default"]
            ),
        ]

    async def execute(
        self,
        query: str,
        search_engine: str = "google",
        browser: str = "default"
    ) -> ToolResult:
        """Search in browser and analyze results"""
        try:
            # First, perform web search to get actual results
            from .web_tools import WebSearchTool
            web_search = WebSearchTool(self.config)
            search_result = await web_search.execute(query, max_results=5)

            # Then open browser with search
            search_tool = SearchBrowserTool(self.config)
            browser_result = await search_tool.execute(query, search_engine, browser)

            if search_result.success and browser_result.success:
                search_data = search_result.result
                results_summary = []

                for result in search_data.get('results', [])[:3]:  # Top 3 results
                    results_summary.append({
                        "title": result.get('title', ''),
                        "snippet": result.get('snippet', ''),
                        "url": result.get('url', '')
                    })

                return ToolResult(
                    success=True,
                    result={
                        "query": query,
                        "browser_opened": True,
                        "search_engine": search_engine,
                        "browser": browser,
                        "search_url": browser_result.result.get('search_url', ''),
                        "top_results": results_summary,
                        "total_results": len(search_data.get('results', [])),
                        "analysis": f"Found {len(search_data.get('results', []))} results for '{query}'. Browser opened with search results.",
                        "message": f"Searched for '{query}' in {browser} browser and analyzed {len(results_summary)} top results"
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    error="Failed to search or open browser"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to search and analyze: {str(e)}"
            )


class BrowserTools:
    """Collection of browser automation tools"""

    def __init__(self, config):
        self.config = config

    def get_tools(self) -> List[BaseTool]:
        """Get all browser tools"""
        return [
            OpenBrowserTool(self.config),
            SearchBrowserTool(self.config),
            SearchAndAnalyzeTool(self.config),
        ]
