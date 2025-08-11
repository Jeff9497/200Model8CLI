# Global Installation Guide for 200Model8CLI

## 🚀 Quick Global Installation

### Method 1: Direct Installation from Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/200Model8CLI.git
cd 200Model8CLI

# Install globally with pip
pip install -e .

# Or install without development mode
pip install .
```

### Method 2: Install from PyPI (When published)

```bash
# This will be available once published to PyPI
pip install 200Model8CLI
```

### Method 3: Install with pipx (Isolated environment)

```bash
# Install pipx if you don't have it
pip install pipx

# Install 200Model8CLI in isolated environment
pipx install 200Model8CLI
```

## ✅ Verify Installation

After installation, you should be able to run from anywhere:

```bash
# Main command
200model8cli --help

# Short alias
m8cli --help

# Test with version
200model8cli version
```

## 🔧 Setup API Key

```bash
# Set your OpenRouter API key
200model8cli set-api-key sk-or-v1-YOUR_API_KEY_HERE

# Or set environment variable
export OPENROUTER_API_KEY="sk-or-v1-YOUR_API_KEY_HERE"
```

## 🎯 Quick Start

```bash
# Switch to best model for tool calling
200model8cli switch

# Test basic functionality
200model8cli ask what files are in this directory

# Test browser automation
200model8cli ask open brave and search for Python tutorials

# Start interactive mode
200model8cli
```

## 📦 Publishing to PyPI (For Maintainers)

```bash
# Build the package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

## 🔄 Updating

```bash
# If installed from source
cd 200Model8CLI
git pull
pip install -e . --upgrade

# If installed from PyPI
pip install --upgrade 200Model8CLI
```

## ❌ Uninstalling

```bash
pip uninstall 200Model8CLI
```

## 🌟 Key Features Available Globally

- **26 Tools**: File ops, web search, browser automation, Git, system commands
- **Multi-Model Support**: Automatic switching to best available models
- **Browser Automation**: Opens Chrome, Firefox, Edge, Brave
- **Agent Mode**: Autonomous multi-step task execution
- **Interactive Mode**: Full conversational AI with tool calling

## 🎯 Recommended Model Priority

The system automatically prioritizes models with excellent tool-calling:
1. `deepseek/deepseek-chat-v3-0324:free` ⭐ **BEST**
2. `deepseek/deepseek-chat:free` ⭐ **GOOD**
3. Other models (tool calling may vary)
