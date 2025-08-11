#  200Model8CLI - The Self-Aware AI Development Assistant

A revolutionary command-line interface that's not just a tool - it's an **intelligent agent that understands and manages its own code**!

🧠 **Self-Aware**: I can analyze, update, and manage my own codebase
🚀 **Multi-Model**: Support for 57+ AI models (OpenRouter, Ollama, Groq)
🔧 **Tool Calling**: Advanced tool calling with local model support
🐙 **GitHub Integration**: Natural language GitHub operations
📚 **Knowledge Management**: Built-in learning and knowledge system
⚡ **Workflow Automation**: Multi-step task automation with templates

## 🌟 Revolutionary Features

### 🧠 **Self-Aware Agent Mode** - *The Game Changer*
```bash
200model8cli self-aware
```

**I am the first CLI that understands itself!** In self-aware mode, I can:

- 📊 **Analyze my own code**: "Analyze your code quality"
- 📝 **Manage my documentation**: "Update your README"
- 🔄 **Create PRs for myself**: "Create a PR for your improvements"

**Natural Language Examples:**
```
🤖 What would you like me to do?
> "Check your own GitHub repository for any issues"
> "Push the latest code changes with a good commit message"
> "Analyze your own code and suggest improvements"
> "Create documentation for your new features"
```

### 🤖 Multi-Model Support
- **Claude 3 Opus/Sonnet** - Anthropic's most capable models
- **GPT-4/GPT-3.5** - OpenAI's flagship models  
- **Llama 3** - Meta's open-source powerhouse
- **Gemini Pro** - Google's advanced AI model
- **Dynamic model switching** during conversations

### 🛠️ Comprehensive Tool System
- **File Operations** - Read, write, edit, search, backup, diff
- **Web Integration** - Search, fetch, extract code from URLs
- **Git & GitHub** - Smart commits, PR creation, branch management
- **Code Analysis** - Syntax checking, formatting, testing
- **System Operations** - Safe command execution, dependency checking

### 💻 Rich CLI Experience
- **Interactive Mode** - Persistent conversations with context
- **Streaming Responses** - Real-time AI interaction
- **Syntax Highlighting** - Beautiful code display
- **Rich Formatting** - Markdown rendering in terminal
- **Progress Indicators** - Visual feedback for long operations

### 🔒 Security & Safety
- **Input Validation** - Sanitized inputs and safe execution
- **Automatic Backups** - File protection before modifications
- **Confirmation Prompts** - User consent for destructive operations
- **Sandboxed Execution** - Safe code running environment

### 🐙 **GitHub Integration** - *Natural Language GitHub Operations*
```bash
# Set your GitHub token
200model8cli set-github-token your_token_here

# Natural language GitHub operations
200model8cli ask "Check the issues in my repository"
200model8cli ask "Create a pull request for the new features"
200model8cli ask "Push my code changes to GitHub"
```

### 📚 **Knowledge Management System**
```bash
# Interactive learning mode
200model8cli learn

# Knowledge management
200model8cli knowledge search "Python async patterns"
200model8cli knowledge add "Best Practices" "Always use async/await..." "coding"
```

### ⚡ **Workflow Automation**
```bash
# Execute workflow templates
200model8cli workflow execute git_feature_workflow
200model8cli workflow list
200model8cli workflow template project_setup
```

### 🤖 **Enhanced Ollama Support**
```bash
# Get model recommendations for tool calling
200model8cli ollama recommend --use-case tool_calling

# Test tool calling capabilities
200model8cli ollama test llama3.1:8b
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Jeff9497/200Model8CLI.git
cd 200Model8CLI

# Install dependencies
pip install -r requirements.txt

# Install the CLI tool
pip install -e .

# Option 1: Set up OpenRouter API key (for cloud models)
export OPENROUTER_API_KEY="your-api-key-here"
200model8cli set-api-key your-openrouter-key

# Option 2: Use local Ollama models (no API key needed)
# Install Ollama from https://ollama.ai
ollama pull qwen3:0.6b  # Fast local model
200model8cli ollama switch  # Switch to local model

# Option 3: Set up Groq API key (for fast cloud models)
200model8cli set-groq-key your-groq-key
```

### Basic Usage

```bash
# Quick Start Options:

# 1. Start with local Ollama models (no API key needed)
200model8cli ollama list          # See available local models
200model8cli ollama switch        # Switch to a local model
200model8cli                      # Start interactive mode

# 2. Start with cloud models (requires API key)
200model8cli switch               # Choose from 56+ free OpenRouter models
200model8cli groq switch          # Choose from 17 fast Groq models
200model8cli                      # Start interactive mode

# File operations
200model8cli edit ./src/main.py "Add error handling to the login function"
200model8cli create ./tests/test_auth.py "Unit tests for authentication module"

# Git operations
200model8cli git commit "Added user authentication system"
200model8cli github pr "Create PR for user authentication feature"

# Web search and fetch
200model8cli search "Python async best practices"
200model8cli fetch https://github.com/user/repo/blob/main/example.py
```

## Configuration

The CLI uses a YAML configuration file located at `~/.200model8cli/config.yaml`:

```yaml
api:
  openrouter_key: ${OPENROUTER_API_KEY}
  base_url: https://openrouter.ai/api/v1
  timeout: 30
  max_retries: 3

models:
  default: claude-3-sonnet
  available:
    - claude-3-opus
    - claude-3-sonnet
    - gpt-4
    - gpt-3.5

tools:
  web_search:
    enabled: true
    max_results: 5
  file_operations:
    enabled: true
    max_file_size: 10MB

ui:
  streaming: true
  syntax_highlighting: true
  rich_formatting: true
```

## Advanced Features

### Smart File Editing
```bash
# Edit multiple related files
200model8cli edit-related "Add logging to all API endpoints" ./src/routes/

# Refactor across files
200model8cli refactor "Rename User class to Account" ./src/

# Create project structure
200model8cli scaffold "Python FastAPI project with JWT auth and PostgreSQL"
```

### Git Workflow Integration
```bash
# AI-generated commit messages
200model8cli git auto-commit

# Smart branch management
200model8cli git workflow "standard feature branch workflow"

# Deploy via GitHub Actions
200model8cli deploy "Deploy to production"
```

### Session Management
```bash
# Save current session
200model8cli session save "feature-development"

# Load previous session
200model8cli session load "feature-development"

# List all sessions
200model8cli session list
```

## Development

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/Jeff9497/200Model8CLI/issues)
- 💬 [Discussions](https://github.com/Jeff9497/200Model8CLI/discussions)
- 🌟 [GitHub Repository](https://github.com/Jeff9497/200Model8CLI)
