# Security Guidelines for 200Model8CLI

## 🔐 API Key Security

### ✅ Safe Practices
- **Never commit API keys to version control**
- Use environment variables or secure config files
- Store keys in `~/.200model8cli/config.yaml` (automatically gitignored)
- Use the CLI commands to set keys: `200model8cli set-api-key YOUR_KEY`

### ❌ Avoid These Mistakes
- Don't hardcode API keys in source code
- Don't share config files containing keys
- Don't commit `.env` files with keys
- Don't paste keys in public forums or issues

## 🛡️ Built-in Security Features

### Input Validation
- All user inputs are validated before processing
- File operations are restricted to safe extensions
- Command execution has safety checks

### Sandboxing
- File operations are limited to current directory by default
- Destructive operations require confirmation
- Automatic backups before file modifications

### Rate Limiting
- API calls are rate-limited to prevent abuse
- Timeout protection for long-running operations
- Retry logic with exponential backoff

## 🚨 Security Considerations

### File Operations
- The CLI can read, write, and execute files
- Always review file operations before confirming
- Use in trusted directories only

### Web Access
- The CLI can make web requests and open browsers
- URLs are validated against allowed domains
- Be cautious with untrusted websites

### System Commands
- Limited system command execution capability
- Blocked dangerous commands (rm -rf, format, etc.)
- Always review system operations

## 🔒 Configuration Security

### Config File Location
```
~/.200model8cli/config.yaml  # Automatically protected by .gitignore
```

### Environment Variables
```bash
# Recommended approach
export OPENROUTER_API_KEY="your-key-here"
export GROQ_API_KEY="your-groq-key-here"
```

### Secure Key Storage
- Keys are encrypted at rest when possible
- Config files have restricted permissions
- Temporary files are cleaned up automatically

## 🚫 Blocked Operations

The CLI automatically blocks these dangerous patterns:
- `rm -rf` (recursive deletion)
- `del /f` (force deletion)
- `format` (disk formatting)
- `fdisk` (disk partitioning)
- Fork bombs and similar

## 📋 Security Checklist

Before using 200Model8CLI:
- [ ] Set API keys using secure methods
- [ ] Review file permissions in working directory
- [ ] Understand what operations you're authorizing
- [ ] Keep the CLI updated to latest version
- [ ] Use in trusted environments only

## 🐛 Reporting Security Issues

If you find security vulnerabilities:
1. **DO NOT** create public GitHub issues
2. Email security concerns privately
3. Include detailed reproduction steps
4. Allow time for fixes before disclosure

## 🔄 Regular Security Maintenance

- Rotate API keys periodically
- Review and clean up old config files
- Update to latest CLI version regularly
- Monitor API usage for anomalies

---

**Remember**: This CLI has powerful capabilities. Use responsibly and always verify operations before execution.
