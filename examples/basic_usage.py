#!/usr/bin/env python3
"""
Basic usage example for 200Model8CLI

Demonstrates how to use the CLI programmatically.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from model8cli.core.config import Config
from model8cli.core.api import OpenRouterClient
from model8cli.core.models import ModelManager
from model8cli.core.session import SessionManager
from model8cli.tools.base import ToolRegistry
from model8cli.tools.file_ops import FileOperations
from model8cli.tools.web_tools import WebTools
from model8cli.tools.git_tools import GitTools
from model8cli.tools.system_tools import SystemTools
from model8cli.tools.code_tools import CodeTools


async def main():
    """Basic usage example"""
    print("200Model8CLI - Basic Usage Example")
    print("=" * 40)
    
    try:
        # Load configuration
        config = Config()
        print(f"✓ Configuration loaded")
        print(f"  Default model: {config.default_model}")
        print(f"  API timeout: {config.api_timeout}s")
        
        # Initialize API client
        async with OpenRouterClient(config) as api_client:
            print("✓ API client initialized")
            
            # Test API connection
            if await api_client.health_check():
                print("✓ API connection healthy")
            else:
                print("✗ API connection failed")
                return
            
            # Initialize model manager
            model_manager = ModelManager(config, api_client)
            await model_manager.initialize()
            print(f"✓ Model manager initialized with {len(model_manager.get_available_models())} models")
            
            # Initialize session manager
            session_manager = SessionManager(config)
            session = session_manager.create_session(
                name="Example Session",
                description="Basic usage example"
            )
            print(f"✓ Session created: {session.metadata.name}")
            
            # Initialize tool registry
            tool_registry = ToolRegistry(config)
            
            # Register all tools
            file_ops = FileOperations(config)
            for tool in file_ops.get_tools():
                tool_registry.register_tool(tool)

            web_tools = WebTools(config)
            for tool in web_tools.get_tools():
                tool_registry.register_tool(tool)

            git_tools = GitTools(config)
            for tool in git_tools.get_tools():
                tool_registry.register_tool(tool)

            system_tools = SystemTools(config)
            for tool in system_tools.get_tools():
                tool_registry.register_tool(tool)

            code_tools = CodeTools(config)
            for tool in code_tools.get_tools():
                tool_registry.register_tool(tool)
            
            print(f"✓ Tool registry initialized with {len(tool_registry.get_enabled_tools())} tools")
            
            # Demonstrate file operations
            print("\nDemonstrating file operations:")
            
            # Create a test file
            test_content = """# Test File
This is a test file created by 200Model8CLI.

## Features
- File reading and writing
- Content search
- Backup creation
- Diff comparison

```python
def hello_world():
    print("Hello from 200Model8CLI!")
```
"""
            
            # Write file
            result = await tool_registry.execute_tool(
                "write_file",
                path="test_example.md",
                content=test_content,
                create_backup=False
            )
            
            if result.success:
                print(f"  ✓ File written: {result.result['path']}")
                print(f"    Size: {result.result['size_formatted']}")
            else:
                print(f"  ✗ Write failed: {result.error}")
                return
            
            # Read file back
            result = await tool_registry.execute_tool(
                "read_file",
                path="test_example.md"
            )
            
            if result.success:
                print(f"  ✓ File read successfully")
                print(f"    Lines: {result.result['line_count']}")
                print(f"    Language: {result.result['language']}")
            else:
                print(f"  ✗ Read failed: {result.error}")
            
            # Search for content
            result = await tool_registry.execute_tool(
                "search_files",
                directory=".",
                content="200Model8CLI",
                max_results=5
            )
            
            if result.success:
                results = result.result['results']
                print(f"  ✓ Search completed: {len(results)} results found")
                for item in results[:3]:
                    print(f"    - {item['path']} ({item['type']})")
            else:
                print(f"  ✗ Search failed: {result.error}")
            
            # Demonstrate AI chat (if API key is configured)
            if config.openrouter_api_key and config.openrouter_api_key != "":
                print("\nDemonstrating AI chat:")
                
                # Add user message
                session_manager.add_message("user", "Hello! Can you help me understand what 200Model8CLI is?")
                
                # Get context messages
                context_messages = session_manager.get_context_messages()
                
                # Get tool definitions
                tool_definitions = tool_registry.get_tool_definitions()
                
                # Make API call
                response = await api_client.chat_completion(
                    messages=context_messages,
                    tools=tool_definitions if tool_definitions else None,
                    max_tokens=500
                )
                
                if response.choices:
                    assistant_message = response.choices[0]["message"]["content"]
                    print(f"  ✓ AI Response received ({len(assistant_message)} chars)")
                    print(f"    Preview: {assistant_message[:100]}...")
                    
                    # Add to session
                    session_manager.add_message("assistant", assistant_message)
                    
                    print(f"  ✓ Session now has {len(session.messages)} messages")
                else:
                    print("  ✗ No response received")
            else:
                print("\nSkipping AI chat demo (no API key configured)")
                print("Set OPENROUTER_API_KEY environment variable to test AI features")
            
            # Show session stats
            print(f"\nSession Statistics:")
            print(f"  Messages: {session.metadata.total_messages}")
            print(f"  Tokens: {session.metadata.total_tokens}")
            print(f"  Model: {session.metadata.model}")
            
            # Show tool stats
            print(f"\nTool Statistics:")
            registry_stats = tool_registry.get_registry_stats()
            print(f"  Total tools: {registry_stats['total_tools']}")
            print(f"  Enabled tools: {registry_stats['enabled_tools']}")
            
            for tool_stat in registry_stats['tools']:
                if tool_stat['execution_count'] > 0:
                    print(f"  {tool_stat['name']}: {tool_stat['execution_count']} executions, "
                          f"{tool_stat['success_rate']:.1%} success rate")
            
            print("\n✓ Example completed successfully!")
            
    except Exception as e:
        print(f"\n✗ Example failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
