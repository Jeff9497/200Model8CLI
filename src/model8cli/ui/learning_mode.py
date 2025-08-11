"""
Interactive Learning Mode for 200Model8CLI

Provides guided learning experiences and explanations.
"""

import asyncio
from typing import Dict, List, Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

import structlog

from ..core.config import Config
from ..core.api import OpenRouterClient
from ..core.models import ModelManager
from ..tools.knowledge_tools import KnowledgeDatabase, KnowledgeEntry
from ..tools.base import ToolRegistry

logger = structlog.get_logger(__name__)
console = Console()


class LearningMode:
    """Interactive learning mode"""
    
    def __init__(self, config: Config, api_client: OpenRouterClient, model_manager: ModelManager, tool_registry: ToolRegistry):
        self.config = config
        self.api_client = api_client
        self.model_manager = model_manager
        self.tool_registry = tool_registry
        self.knowledge_db = KnowledgeDatabase(config.config_dir / "knowledge.db")
        
        # Learning topics
        self.topics = {
            "cli_basics": {
                "title": "CLI Basics",
                "description": "Learn the fundamentals of using 200Model8CLI",
                "lessons": [
                    "Getting started with interactive mode",
                    "Using file operations",
                    "Working with models",
                    "Understanding tool calling"
                ]
            },
            "git_workflow": {
                "title": "Git Workflow",
                "description": "Master Git operations with AI assistance",
                "lessons": [
                    "Basic Git commands",
                    "AI-generated commit messages",
                    "Branch management",
                    "GitHub integration"
                ]
            },
            "web_automation": {
                "title": "Web Automation",
                "description": "Learn web search and browser automation",
                "lessons": [
                    "Web search techniques",
                    "Browser automation",
                    "Content extraction",
                    "Research workflows"
                ]
            },
            "code_analysis": {
                "title": "Code Analysis",
                "description": "Understand code analysis and improvement",
                "lessons": [
                    "Code review with AI",
                    "Automated testing",
                    "Code formatting",
                    "Performance optimization"
                ]
            },
            "advanced_features": {
                "title": "Advanced Features",
                "description": "Explore advanced 200Model8CLI capabilities",
                "lessons": [
                    "Session management",
                    "Custom workflows",
                    "Agent mode",
                    "Knowledge management"
                ]
            }
        }
    
    async def start_learning_mode(self):
        """Start interactive learning mode"""
        console.print(Panel(
            "[bold blue]🎓 Welcome to 200Model8CLI Learning Mode![/bold blue]\n\n"
            "This interactive mode will help you learn how to use 200Model8CLI effectively.\n"
            "You can explore different topics, get explanations, and practice with real examples.",
            title="Learning Mode",
            border_style="blue"
        ))
        
        while True:
            try:
                choice = await self._show_main_menu()
                
                if choice == "topics":
                    await self._explore_topics()
                elif choice == "search":
                    await self._search_knowledge()
                elif choice == "practice":
                    await self._practice_mode()
                elif choice == "quiz":
                    await self._quiz_mode()
                elif choice == "help":
                    await self._show_help()
                elif choice == "exit":
                    console.print("[green]Thanks for learning! Happy coding! 🚀[/green]")
                    break
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Learning mode interrupted. Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error in learning mode: {e}[/red]")
    
    async def _show_main_menu(self) -> str:
        """Show main learning menu"""
        console.print("\n[bold cyan]📚 Learning Menu:[/bold cyan]")
        console.print("1. [blue]topics[/blue]   - Explore learning topics")
        console.print("2. [blue]search[/blue]   - Search knowledge base")
        console.print("3. [blue]practice[/blue] - Practice with examples")
        console.print("4. [blue]quiz[/blue]     - Test your knowledge")
        console.print("5. [blue]help[/blue]     - Get help and tips")
        console.print("6. [blue]exit[/blue]     - Exit learning mode")
        
        choice = Prompt.ask("\nWhat would you like to do?", 
                          choices=["topics", "search", "practice", "quiz", "help", "exit"],
                          default="topics")
        return choice
    
    async def _explore_topics(self):
        """Explore learning topics"""
        console.print("\n[bold cyan]📖 Available Topics:[/bold cyan]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Topic", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Lessons", style="yellow")
        
        for topic_id, topic in self.topics.items():
            table.add_row(
                topic["title"],
                topic["description"],
                str(len(topic["lessons"]))
            )
        
        console.print(table)
        
        topic_choice = Prompt.ask("\nWhich topic would you like to explore?",
                                choices=list(self.topics.keys()) + ["back"],
                                default="back")
        
        if topic_choice != "back":
            await self._explore_topic(topic_choice)
    
    async def _explore_topic(self, topic_id: str):
        """Explore a specific topic"""
        topic = self.topics[topic_id]
        
        console.print(Panel(
            f"[bold]{topic['title']}[/bold]\n\n{topic['description']}",
            title="Topic Overview",
            border_style="cyan"
        ))
        
        console.print("\n[bold cyan]📝 Lessons:[/bold cyan]")
        for i, lesson in enumerate(topic["lessons"], 1):
            console.print(f"{i}. {lesson}")
        
        lesson_choice = Prompt.ask(f"\nWhich lesson (1-{len(topic['lessons'])}) or 'back'?",
                                 default="back")
        
        if lesson_choice != "back" and lesson_choice.isdigit():
            lesson_idx = int(lesson_choice) - 1
            if 0 <= lesson_idx < len(topic["lessons"]):
                await self._show_lesson(topic_id, lesson_idx)
    
    async def _show_lesson(self, topic_id: str, lesson_idx: int):
        """Show a specific lesson"""
        topic = self.topics[topic_id]
        lesson_title = topic["lessons"][lesson_idx]
        
        console.print(Panel(
            f"[bold blue]Lesson: {lesson_title}[/bold blue]",
            title=f"{topic['title']} - Lesson {lesson_idx + 1}",
            border_style="blue"
        ))
        
        # Generate lesson content using AI
        await self._generate_lesson_content(topic_id, lesson_title)
        
        # Ask if user wants to practice
        if Confirm.ask("\nWould you like to try a practical example?"):
            await self._show_practical_example(topic_id, lesson_title)
    
    async def _generate_lesson_content(self, topic_id: str, lesson_title: str):
        """Generate lesson content using AI"""
        try:
            prompt = f"""
            Create a comprehensive lesson about "{lesson_title}" for 200Model8CLI users.
            
            The lesson should include:
            1. Clear explanation of the concept
            2. Step-by-step instructions
            3. Common use cases
            4. Best practices
            5. Tips and tricks
            
            Keep it practical and focused on 200Model8CLI features.
            Format the response in markdown.
            """
            
            from ..core.api import Message
            messages = [Message(role="user", content=prompt)]
            
            response = await self.api_client.chat_completion(
                messages=messages,
                max_tokens=1000
            )
            
            if response.choices:
                content = response.choices[0].message.content
                markdown = Markdown(content)
                console.print(Panel(markdown, title="Lesson Content", border_style="green"))
            
        except Exception as e:
            console.print(f"[red]Failed to generate lesson content: {e}[/red]")
            # Fallback to basic content
            console.print(Panel(
                f"This lesson covers {lesson_title}. "
                f"It's an important topic for mastering 200Model8CLI.",
                title="Lesson Content",
                border_style="yellow"
            ))
    
    async def _show_practical_example(self, topic_id: str, lesson_title: str):
        """Show practical example for the lesson"""
        examples = {
            "cli_basics": {
                "Getting started with interactive mode": "200model8cli\n# Then try: ask 'What can you help me with?'",
                "Using file operations": "200model8cli read README.md\n200model8cli write test.txt 'Hello World'",
                "Working with models": "200model8cli models\n200model8cli switch",
                "Understanding tool calling": "200model8cli ask 'List files in current directory'"
            },
            "git_workflow": {
                "Basic Git commands": "200model8cli ask 'Check git status and commit changes'",
                "AI-generated commit messages": "200model8cli ask 'Create a commit with AI-generated message'",
                "Branch management": "200model8cli ask 'Create a new feature branch'",
                "GitHub integration": "200model8cli github create-repo my-project"
            }
        }
        
        if topic_id in examples and lesson_title in examples[topic_id]:
            example = examples[topic_id][lesson_title]
            console.print(Panel(
                f"[bold green]Try this example:[/bold green]\n\n[code]{example}[/code]",
                title="Practical Example",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"Practice using 200Model8CLI features related to: {lesson_title}",
                title="Practice Suggestion",
                border_style="yellow"
            ))
    
    async def _search_knowledge(self):
        """Search the knowledge base"""
        query = Prompt.ask("What would you like to search for?")
        
        if query:
            entries = self.knowledge_db.search_entries(query, limit=5)
            
            if entries:
                console.print(f"\n[green]Found {len(entries)} results for '{query}':[/green]")
                
                for i, entry in enumerate(entries, 1):
                    console.print(Panel(
                        f"[bold]{entry.title}[/bold]\n\n{entry.content[:300]}...",
                        title=f"Result {i} - {entry.category}",
                        border_style="cyan"
                    ))
            else:
                console.print(f"[yellow]No results found for '{query}'[/yellow]")
                
                # Offer to add knowledge
                if Confirm.ask("Would you like to add this as a new knowledge entry?"):
                    await self._add_knowledge_entry(query)
    
    async def _add_knowledge_entry(self, query: str):
        """Add a new knowledge entry"""
        title = Prompt.ask("Enter title for the knowledge entry", default=query)
        content = Prompt.ask("Enter content")
        category = Prompt.ask("Enter category", default="general")
        tags_input = Prompt.ask("Enter tags (comma-separated)", default="")
        
        tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]
        
        from ..tools.knowledge_tools import AddKnowledgeTool
        tool = AddKnowledgeTool(self.config)
        
        result = await tool.execute(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source="learning_mode"
        )
        
        if result.success:
            console.print("[green]✅ Knowledge entry added successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to add knowledge entry: {result.error}[/red]")
    
    async def _practice_mode(self):
        """Practice mode with guided exercises"""
        console.print(Panel(
            "[bold blue]🏋️ Practice Mode[/bold blue]\n\n"
            "Try these exercises to improve your 200Model8CLI skills:",
            title="Practice",
            border_style="blue"
        ))
        
        exercises = [
            "Use the file operations to create and read a file",
            "Search for information about Python programming",
            "Check the status of a Git repository",
            "List available AI models and switch to a different one",
            "Create a simple workflow using multiple tools"
        ]
        
        for i, exercise in enumerate(exercises, 1):
            console.print(f"{i}. {exercise}")
        
        choice = Prompt.ask(f"Which exercise (1-{len(exercises)}) would you like to try?",
                          default="1")
        
        if choice.isdigit() and 1 <= int(choice) <= len(exercises):
            exercise = exercises[int(choice) - 1]
            console.print(Panel(
                f"[bold green]Exercise:[/bold green] {exercise}\n\n"
                f"Try to complete this exercise using 200Model8CLI commands.",
                title="Practice Exercise",
                border_style="green"
            ))
    
    async def _quiz_mode(self):
        """Quiz mode to test knowledge"""
        console.print(Panel(
            "[bold blue]🧠 Quiz Mode[/bold blue]\n\n"
            "Test your knowledge of 200Model8CLI!",
            title="Quiz",
            border_style="blue"
        ))
        
        questions = [
            {
                "question": "What command starts interactive mode?",
                "options": ["200model8cli", "200model8cli interactive", "200model8cli start"],
                "correct": 0
            },
            {
                "question": "How do you list available models?",
                "options": ["200model8cli list", "200model8cli models", "200model8cli show"],
                "correct": 1
            },
            {
                "question": "What tool category handles file operations?",
                "options": ["system_tools", "file_ops", "web_tools"],
                "correct": 1
            }
        ]
        
        score = 0
        for i, q in enumerate(questions, 1):
            console.print(f"\n[bold cyan]Question {i}:[/bold cyan] {q['question']}")
            
            for j, option in enumerate(q['options']):
                console.print(f"{j + 1}. {option}")
            
            answer = Prompt.ask("Your answer (1-3)", choices=["1", "2", "3"])
            
            if int(answer) - 1 == q['correct']:
                console.print("[green]✅ Correct![/green]")
                score += 1
            else:
                correct_answer = q['options'][q['correct']]
                console.print(f"[red]❌ Incorrect. The correct answer is: {correct_answer}[/red]")
        
        console.print(Panel(
            f"[bold]Quiz Complete![/bold]\n\nYour score: {score}/{len(questions)}",
            title="Results",
            border_style="green" if score == len(questions) else "yellow"
        ))
    
    async def _show_help(self):
        """Show help and tips"""
        console.print(Panel(
            "[bold blue]💡 Tips and Help[/bold blue]\n\n"
            "• Use 'ask' command for natural language requests\n"
            "• Try 'switch' to change AI models\n"
            "• Use 'agent' mode for complex tasks\n"
            "• Check 'github' commands for repository management\n"
            "• Explore 'knowledge' tools for information management\n\n"
            "[bold]Need more help?[/bold]\n"
            "• Type '200model8cli --help' for command reference\n"
            "• Use interactive mode for guided assistance\n"
            "• Check the documentation for detailed guides",
            title="Help & Tips",
            border_style="blue"
        ))
