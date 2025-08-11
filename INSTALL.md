# 🚀 200Model8CLI Global Installation Guide

## 📋 Prerequisites

- **Python 3.8+** (Check with `python --version`)
- **pip** (Python package manager)
- **OpenRouter API Key** (Get from https://openrouter.ai/)

## 🎯 Installation Methods

### Method 1: Direct Installation (Recommended)

1. **Download the source code** (as ZIP or clone)
2. **Navigate to the directory**:
   ```bash
   cd 200Model8CLI
   ```
3. **Install globally**:
   ```bash
   pip install -e .
   ```
4. **Set your API key**:
   ```bash
   200model8cli set-api-key YOUR_OPENROUTER_API_KEY
   ```
5. **Start using**:
   ```bash
   200model8cli
   ```

### Method 2: Using the Install Script

1. **Run the installer**:
   ```bash
   python install.py
   ```
2. **Follow the prompts** to complete setup

### Method 3: Manual Installation

1. **Install dependencies**:
   ```bash
   pip install click httpx rich pyyaml aiofiles python-dotenv tiktoken pygments asyncio-throttle pathspec watchdog GitPython beautifulsoup4 requests urllib3 cryptography keyring configparser toml prompt-toolkit colorama tabulate jsonschema marshmallow structlog loguru cachetools diskcache
   ```
2. **Install the package**:
   ```bash
   pip install -e .
   ```

## 🔑 API Key Setup

### Option 1: Using the CLI
```bash
200model8cli set-api-key sk-or-v1-YOUR_API_KEY_HERE
```

### Option 2: Environment Variable
```bash
# Windows (PowerShell)
$env:OPENROUTER_API_KEY="sk-or-v1-YOUR_API_KEY_HERE"

# Linux/Mac
export OPENROUTER_API_KEY="sk-or-v1-YOUR_API_KEY_HERE"
```

## 🧪 Testing Installation

```bash
# Check version
200model8cli --version

# List available commands
200model8cli --help

# Test with a simple command
200model8cli switch --list

# Start interactive mode
200model8cli
```

## 🌟 Quick Start

1. **Switch to a working model**:
   ```bash
   200model8cli switch
   ```

2. **Run Python code**:
   ```bash
   200model8cli run-python "print('Hello World!')"
   ```

3. **Search the web**:
   ```bash
   200model8cli search "Python tutorials"
   ```

4. **Ask AI naturally**:
   ```bash
   200model8cli ask create a Python hello world program
   ```

5. **Start interactive chat**:
   ```bash
   200model8cli
   ```

## 🔧 Troubleshooting

### Installation Issues

**Problem**: `pip install -e .` fails
**Solution**: 
```bash
pip install --upgrade pip
pip install -e . --verbose
```

**Problem**: Command not found after installation
**Solution**: 
```bash
# Add Python Scripts to PATH (Windows)
# Or restart your terminal

# Check if installed
pip list | grep 200Model8CLI
```

### API Key Issues

**Problem**: "API key is required" error
**Solution**: 
```bash
200model8cli set-api-key YOUR_KEY
# Or set environment variable
```

**Problem**: "Invalid API key" error
**Solution**: 
- Verify your key starts with `sk-or-v1-`
- Check https://openrouter.ai/ for valid key

### Model Issues

**Problem**: "Model not available" error
**Solution**: 
```bash
200model8cli switch  # Auto-switch to working model
200model8cli models  # List all models
```

## 🎉 You're Ready!

Once installed, you have access to:

- **🤖 6+ Free AI Models** - Switch easily between models
- **💻 Terminal Integration** - Execute commands through AI
- **🐍 Python Execution** - Run code files and strings
- **🌐 Web Search** - Free search capabilities
- **📁 File Management** - Create, edit, analyze files
- **🔧 Code Analysis** - Syntax checking and suggestions
- **📊 System Monitoring** - Process and performance info

**Start your AI coding journey**: `200model8cli` 🚀

## 📚 Advanced Features

- **Ollama Support**: Use local models (coming soon)
- **Browser Automation**: Open URLs and search directly
- **Loop Detection**: Automatic stability improvements
- **Fast Startup**: Optimized model loading

## 🆘 Need Help?

- Run `200model8cli --help` for all commands
- Use `200model8cli ask help me understand this tool`
- Check the README.md for detailed documentation

**Happy Coding!** 🎯
