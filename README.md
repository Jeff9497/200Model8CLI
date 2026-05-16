# 200Model8CLI

A self-aware, self-improving personal AI agent. Runs on any machine — including Android via Termux. Talk to it from Telegram. It remembers everything, learns from every task, and proposes fixes to its own code for your approval.

---

## What it does

- **Persistent memory** — SQLite file remembers conversations, lessons, and preferences across sessions
- **Skill capture** — solves a task once, saves it as a reusable skill, executes faster next time
- **Self-improvement** — reads its own error logs, proposes diffs, waits for your approval before applying
- **Reflection** — scores itself after every task and logs what it learned
- **Telegram bot** — talk from your phone, approve/reject code patches, receive daily summary
- **Time-based instructions** — "suggest a song in 3 hours" — just say it naturally
- **End-of-day summary** — every day at 21:00 it sends what it learned that day
- **Any model** — OpenRouter (200+ models, free tier), Groq, or Ollama (local/offline)

---

## Install

```bash
# From GitHub
pip install git+https://github.com/Jeff9497/200Model8CLI

# Or clone locally
git clone https://github.com/Jeff9497/200Model8CLI
cd 200Model8CLI
pip install -e .
```

### Android (Termux)
```bash
pkg install python git
pip install git+https://github.com/Jeff9497/200Model8CLI
```

---

## Configuration

Create `.env` in your working directory:

```env
# Required
OPENROUTER_API_KEY=sk-or-...

# Free model (no cost)
MODEL8CLI_DEFAULT_MODEL=meta-llama/llama-3.3-70b-instruct:free

# For self-patching
GITHUB_TOKEN=ghp_...

# For Telegram bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Get Telegram credentials:
1. Message `@BotFather` → `/newbot` → copy token
2. Message `@userinfobot` → copy your chat ID

---

## Usage

### CLI
```bash
200model8cli self-aware
```
Inside: just talk. Special commands: `improve`, `skills`, `summary`, `exit`

### Telegram bot
```bash
200model8cli bot
```
Bot commands: `/skills` `/memory` `/improve` `/summary`

### Time instructions (both modes)
```
"suggest a song in 3 hours"
"remind me to review the PR in 2 hours"
```

---

## Model routing

| Use case | Model |
|---|---|
| Free cloud | `meta-llama/llama-3.3-70b-instruct:free` |
| Best free reasoning | `deepseek/deepseek-r1:free` |
| Offline phone (light) | `ollama/qwen2.5:1b` |
| Offline phone (better) | `ollama/llama3.2:3b` |

---

## Memory

Single file: `~/.200model8cli/memory.db`

| Table | Stores |
|---|---|
| `conversations` | Every message, searchable |
| `skills` | Saved workflows |
| `lessons` | Errors and fixes |
| `user_model` | Your preferences |
| `scheduled_tasks` | Pending reminders |
| `daily_log` | Today's activity |

---

## Self-improvement flow

```
improve → reads error logs → AST analysis → diff proposed
→ you approve/reject → patch applied → tested → committed
→ lesson saved to memory
```

Nothing applied without your approval.

---

## License

MIT
