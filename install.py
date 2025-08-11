#!/usr/bin/env python3
"""
Installation script for 200Model8CLI

Installs the CLI tool and sets up the environment.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {command}")
        print(f"   Error: {e.stderr}")
        return False


def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True


def install_dependencies():
    """Install Python dependencies"""
    commands = [
        ("pip install --upgrade pip", "Upgrading pip"),
        ("pip install -r requirements.txt", "Installing dependencies"),
        ("pip install -e .", "Installing 200Model8CLI in development mode"),
    ]
    
    for command, description in commands:
        if not run_command(command, description):
            return False
    
    return True


def setup_config():
    """Setup initial configuration"""
    print("🔧 Setting up configuration...")
    
    config_dir = Path.home() / ".200model8cli"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "config.yaml"
    
    if not config_file.exists():
        # Create default config
        default_config = """# 200Model8CLI Configuration
api:
  openrouter_key: ${OPENROUTER_API_KEY}
  base_url: https://openrouter.ai/api/v1
  timeout: 30
  max_retries: 3

models:
  default: deepseek/deepseek-chat-v3-0324:free
  available:
    - anthropic/claude-3-opus
    - anthropic/claude-3-sonnet-20240229
    - anthropic/claude-3-haiku-20240307
    - openai/gpt-4-turbo
    - openai/gpt-4
    - openai/gpt-3.5-turbo
    - meta-llama/llama-3-70b-instruct
    - google/gemini-pro
    - moonshotai/kimi-k2:free
    - featherless/qwerky-72b:free
    - deepseek/deepseek-r1-0528:free
    - deepseek/deepseek-chat-v3-0324:free
    - google/gemma-3-27b-it:free
    - deepseek/deepseek-r1:free

tools:
  web_search_enabled: true
  file_operations_enabled: true
  git_operations_enabled: true
  system_operations_enabled: true

ui:
  streaming: true
  syntax_highlighting: true
  rich_formatting: true
  interactive_mode: true

security:
  validate_inputs: true
  confirm_destructive_ops: true
  backup_before_edit: true

logging:
  level: INFO
  file_enabled: true
  console_enabled: true
"""
        
        with open(config_file, 'w') as f:
            f.write(default_config)
        
        print(f"✅ Created default config: {config_file}")
    else:
        print(f"✅ Config already exists: {config_file}")
    
    return True


def check_api_key():
    """Check if API key is configured"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        print("⚠️  OpenRouter API key not found")
        print("   Set the OPENROUTER_API_KEY environment variable to use AI features")
        print("   Example: export OPENROUTER_API_KEY='your-api-key-here'")
        print("   Get your API key from: https://openrouter.ai/keys")
        return False
    else:
        print("✅ OpenRouter API key found")
        return True


def test_installation():
    """Test the installation"""
    print("🧪 Testing installation...")
    
    # Test import
    try:
        import model8cli
        print("✅ Package import successful")
    except ImportError as e:
        print(f"❌ Package import failed: {e}")
        return False
    
    # Test CLI command
    if run_command("200model8cli --help", "Testing CLI command"):
        return True
    
    # Try alternative command
    if run_command("m8cli --help", "Testing alternative CLI command"):
        return True
    
    print("❌ CLI command test failed")
    return False


def main():
    """Main installation process"""
    print("🚀 Installing 200Model8CLI - OpenRouter CLI Agent")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Installation failed during dependency installation")
        sys.exit(1)
    
    # Setup configuration
    if not setup_config():
        print("❌ Installation failed during configuration setup")
        sys.exit(1)
    
    # Check API key
    api_key_configured = check_api_key()
    
    # Test installation
    if not test_installation():
        print("❌ Installation test failed")
        sys.exit(1)
    
    print("\n🎉 Installation completed successfully!")
    print("\n📖 Quick Start:")
    print("   1. Set your OpenRouter API key:")
    print("      export OPENROUTER_API_KEY='your-api-key-here'")
    print("   2. Start interactive mode:")
    print("      200model8cli")
    print("   3. Or use specific commands:")
    print("      200model8cli read ./file.py")
    print("      200model8cli write ./output.txt 'Hello World'")
    print("      200model8cli search --content 'function' --directory ./src")
    
    if not api_key_configured:
        print("\n⚠️  Remember to set your OpenRouter API key to use AI features!")
    
    print("\n📚 Documentation: README.md")
    print("🐛 Issues: https://github.com/yourusername/200Model8CLI/issues")


if __name__ == "__main__":
    main()
