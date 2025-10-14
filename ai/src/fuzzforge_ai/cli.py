# ruff: noqa: E402  # Imports delayed for environment/logging setup
#!/usr/bin/env python3
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

"""
FuzzForge CLI - Clean modular version
Uses the separated agent components
"""

import asyncio
import shlex
import os
import sys
import signal
import warnings
import logging
import random
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

# Ensure Cognee writes logs inside the project workspace
project_root = Path.cwd()
default_log_dir = project_root / ".fuzzforge" / "logs"
default_log_dir.mkdir(parents=True, exist_ok=True)
log_path = default_log_dir / "cognee.log"
os.environ.setdefault("COGNEE_LOG_PATH", str(log_path))

# Suppress warnings
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR)

# Load .env file with explicit path handling
# 1. First check current working directory for .fuzzforge/.env
fuzzforge_env = Path.cwd() / ".fuzzforge" / ".env"
if fuzzforge_env.exists():
    load_dotenv(fuzzforge_env, override=True)
else:
    # 2. Then check parent directories for .fuzzforge projects
    current_path = Path.cwd()
    for parent in [current_path] + list(current_path.parents):
        fuzzforge_dir = parent / ".fuzzforge"
        if fuzzforge_dir.exists():
            project_env = fuzzforge_dir / ".env"
            if project_env.exists():
                load_dotenv(project_env, override=True)
                break
    else:
        # 3. Fallback to generic load_dotenv
        load_dotenv(override=True)

# Enhanced readline configuration for Rich Console input compatibility
try:
    import readline
    # Enable Rich-compatible input features
    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode emacs")
    readline.parse_and_bind("set show-all-if-ambiguous on") 
    readline.parse_and_bind("set completion-ignore-case on")
    readline.parse_and_bind("set colored-completion-prefix on")
    readline.parse_and_bind("set enable-bracketed-paste on")  # Better paste support
    # Navigation bindings for better editing
    readline.parse_and_bind("Control-a: beginning-of-line")
    readline.parse_and_bind("Control-e: end-of-line") 
    readline.parse_and_bind("Control-u: unix-line-discard")
    readline.parse_and_bind("Control-k: kill-line")
    readline.parse_and_bind("Control-w: unix-word-rubout")
    readline.parse_and_bind("Meta-Backspace: backward-kill-word")
    # History and completion
    readline.set_history_length(2000)
    readline.set_startup_hook(None)
    # Enable multiline editing hints
    readline.parse_and_bind("set horizontal-scroll-mode off")
    readline.parse_and_bind("set mark-symlinked-directories on")
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


from .agent import FuzzForgeAgent
from .config_manager import ConfigManager
from .config_bridge import ProjectConfigManager

console = Console()

# Global shutdown flag
shutdown_requested = False

# Dynamic status messages for better UX
THINKING_MESSAGES = [
    "Thinking", "Processing", "Computing", "Analyzing", "Working", 
    "Pondering", "Deliberating", "Calculating", "Reasoning", "Evaluating"
]

WORKING_MESSAGES = [
    "Working", "Processing", "Handling", "Executing", "Running",
    "Operating", "Performing", "Conducting", "Managing", "Coordinating" 
]

SEARCH_MESSAGES = [
    "Searching", "Scanning", "Exploring", "Investigating", "Hunting",
    "Seeking", "Probing", "Examining", "Inspecting", "Browsing"
]

# Cool prompt symbols
PROMPT_STYLES = [
    "▶", "❯", "➤", "→", "»", "⟩", "▷", "⇨", "⟶", "◆"
]

def get_dynamic_status(action_type="thinking"):
    """Get a random status message based on action type"""
    if action_type == "thinking":
        return f"{random.choice(THINKING_MESSAGES)}..."
    elif action_type == "working":
        return f"{random.choice(WORKING_MESSAGES)}..."
    elif action_type == "searching":
        return f"{random.choice(SEARCH_MESSAGES)}..."
    else:
        return f"{random.choice(THINKING_MESSAGES)}..."

def get_prompt_symbol():
    """Get prompt symbol indicating where to write"""
    return ">>"

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    shutdown_requested = True
    console.print("\n\n[yellow]Shutting down gracefully...[/yellow]")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

@contextmanager
def safe_status(message: str):
    """Safe status context manager"""
    status = console.status(message, spinner="dots")
    try:
        status.start()
        yield
    finally:
        status.stop()


class FuzzForgeCLI:
    """Command-line interface for FuzzForge"""
    
    def __init__(self):
        """Initialize the CLI"""
        # Ensure .env is loaded from .fuzzforge directory
        fuzzforge_env = Path.cwd() / ".fuzzforge" / ".env"
        if fuzzforge_env.exists():
            load_dotenv(fuzzforge_env, override=True)
        
        # Load configuration for agent registry
        self.config_manager = ConfigManager()
        
        # Check environment configuration
        if not os.getenv('LITELLM_MODEL'):
            console.print("[red]ERROR: LITELLM_MODEL not set in .env file[/red]")
            console.print("Please set LITELLM_MODEL to your desired model")
            sys.exit(1)
        
        # Create the agent (uses env vars directly)
        self.agent = FuzzForgeAgent()
        
        # Create a consistent context ID for this CLI session
        self.context_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Track registered agents for config persistence
        self.agents_modified = False
        
        # Command handlers
        self.commands = {
            "/help": self.cmd_help,
            "/register": self.cmd_register,
            "/unregister": self.cmd_unregister,
            "/list": self.cmd_list,
            "/memory": self.cmd_memory,
            "/recall": self.cmd_recall,
            "/artifacts": self.cmd_artifacts,
            "/tasks": self.cmd_tasks,
            "/skills": self.cmd_skills,
            "/sessions": self.cmd_sessions,
            "/clear": self.cmd_clear,
            "/sendfile": self.cmd_sendfile,
            "/quit": self.cmd_quit,
            "/exit": self.cmd_quit,
        }

        self.background_tasks: set[asyncio.Task] = set()
        
    def print_banner(self):
        """Print welcome banner"""
        card = self.agent.agent_card
        
        # Print ASCII banner
        console.print("[medium_purple3] ███████╗██╗   ██╗███████╗███████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗     █████╗ ██╗[/medium_purple3]")
        console.print("[medium_purple3] ██╔════╝██║   ██║╚══███╔╝╚══███╔╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝    ██╔══██╗██║[/medium_purple3]")
        console.print("[medium_purple3] █████╗  ██║   ██║  ███╔╝   ███╔╝ █████╗  ██║   ██║██████╔╝██║  ███╗█████╗      ███████║██║[/medium_purple3]")
        console.print("[medium_purple3] ██╔══╝  ██║   ██║ ███╔╝   ███╔╝  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝      ██╔══██║██║[/medium_purple3]")
        console.print("[medium_purple3] ██║     ╚██████╔╝███████╗███████╗██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗    ██║  ██║██║[/medium_purple3]")
        console.print("[medium_purple3] ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝  ╚═╝╚═╝[/medium_purple3]")
        console.print(f"\n[dim]{card.description}[/dim]\n")

        provider = (
            os.getenv("LLM_PROVIDER")
            or os.getenv("LLM_COGNEE_PROVIDER")
            or os.getenv("COGNEE_LLM_PROVIDER")
            or "unknown"
        )

        console.print(
            "LLM Provider: [medium_purple1]{provider}[/medium_purple1]".format(
                provider=provider
            )
        )
        console.print(
            "LLM Model: [medium_purple1]{model}[/medium_purple1]".format(
                model=self.agent.model
            )
        )
        if self.agent.executor.agentops_trace:
            console.print("Tracking: [medium_purple1]AgentOps active[/medium_purple1]")

        # Show skills
        console.print("\nSkills:")
        for skill in card.skills:
            console.print(
                f"   • [deep_sky_blue1]{skill.name}[/deep_sky_blue1] – {skill.description}"
            )
        console.print("\nType /help for commands or just chat\n")
        
    async def cmd_help(self, args: str = "") -> None:
        """Show help"""
        help_text = """
[bold]Commands:[/bold]
  /register <url>  - Register an A2A agent (saves to config)
  /unregister <name> - Remove agent from registry and config
  /list           - List registered agents
  
[bold]Memory Systems:[/bold]  
  /recall <query> - Search past conversations (ADK Memory)
  /memory         - Show knowledge graph (Cognee)
  /memory save    - Save to knowledge graph
  /memory search  - Search knowledge graph
  
[bold]Other:[/bold]
  /artifacts      - List created artifacts
  /artifacts <id> - Show artifact content
  /tasks [id]     - Show task list or details
  /skills         - Show FuzzForge skills
  /sessions       - List active sessions
  /sendfile <agent> <path> [message] - Attach file as artifact and route to agent
  /clear          - Clear screen
  /help           - Show this help
  /quit           - Exit

[bold]Sample prompts:[/bold]
  run fuzzforge workflow security_assessment on /absolute/path --volume-mode ro
  list fuzzforge runs limit=5
  get fuzzforge summary <run_id>
  query project knowledge about "unsafe Rust" using GRAPH_COMPLETION
  export project file src/lib.rs as artifact
  /memory search "recent findings"

[bold]Input Editing:[/bold]
  Arrow keys      - Move cursor
  Ctrl+A/E        - Start/end of line
  Up/Down         - Command history
        """
        console.print(help_text)
        
    async def cmd_register(self, args: str) -> None:
        """Register an agent"""
        if not args:
            console.print("Usage: /register <url>")
            return
            
        with safe_status(f"{get_dynamic_status('working')} Registering {args}"):
            result = await self.agent.register_agent(args.strip())
            
        if result["success"]:
            console.print(f"✅ Registered: [bold]{result['name']}[/bold]")
            console.print(f"   Capabilities: {result['capabilities']} skills")
            
            # Get description from the agent's card
            agents = self.agent.list_agents()
            description = ""
            for agent in agents:
                if agent['name'] == result['name']:
                    description = agent.get('description', '')
                    break
            
            # Add to config for persistence
            self.config_manager.add_registered_agent(
                name=result['name'],
                url=args.strip(),
                description=description
            )
            console.print("   [dim]Saved to config for auto-registration[/dim]")
        else:
            console.print(f"[red]Failed: {result['error']}[/red]")
            
    async def cmd_unregister(self, args: str) -> None:
        """Unregister an agent and remove from config"""
        if not args:
            console.print("Usage: /unregister <name or url>")
            return
        
        # Try to find the agent
        agents = self.agent.list_agents()
        agent_to_remove = None
        
        for agent in agents:
            if agent['name'].lower() == args.lower() or agent['url'] == args:
                agent_to_remove = agent
                break
        
        if not agent_to_remove:
            console.print(f"[yellow]Agent '{args}' not found[/yellow]")
            return
        
        # Remove from config
        if self.config_manager.remove_registered_agent(name=agent_to_remove['name'], url=agent_to_remove['url']):
            console.print(f"✅ Unregistered: [bold]{agent_to_remove['name']}[/bold]")
            console.print("   [dim]Removed from config (won't auto-register next time)[/dim]")
        else:
            console.print("[yellow]Agent unregistered from session but not found in config[/yellow]")
    
    async def cmd_list(self, args: str = "") -> None:
        """List registered agents"""
        agents = self.agent.list_agents()
        
        if not agents:
            console.print("No agents registered. Use /register <url>")
            return
            
        table = Table(title="Registered Agents", box=box.ROUNDED)
        table.add_column("Name", style="medium_purple3")
        table.add_column("URL", style="deep_sky_blue3")
        table.add_column("Skills", style="plum3")
        table.add_column("Description", style="dim")
        
        for agent in agents:
            desc = agent['description']
            if len(desc) > 40:
                desc = desc[:37] + "..."
            table.add_row(
                agent['name'],
                agent['url'],
                str(agent['skills']),
                desc
            )
            
        console.print(table)
        
    async def cmd_recall(self, args: str = "") -> None:
        """Search conversational memory (past conversations)"""
        if not args:
            console.print("Usage: /recall <query>")
            return
        
        await self._sync_conversational_memory()

        # First try MemoryService (for ingested memories)
        with safe_status(get_dynamic_status('searching')):
            results = await self.agent.memory_manager.search_conversational_memory(args)
        
        if results and results.memories:
            console.print(f"[bold]Found {len(results.memories)} memories:[/bold]\n")
            for i, memory in enumerate(results.memories, 1):
                # MemoryEntry has 'text' field, not 'content'
                text = getattr(memory, 'text', str(memory))
                if len(text) > 200:
                    text = text[:200] + "..."
                console.print(f"{i}. {text}")
        else:
            # If MemoryService is empty, search SQLite directly
            console.print("[yellow]No memories in MemoryService, searching SQLite sessions...[/yellow]")
            
            # Check if using DatabaseSessionService
            if hasattr(self.agent.executor, 'session_service'):
                service_type = type(self.agent.executor.session_service).__name__
                if service_type == 'DatabaseSessionService':
                    # Search SQLite database directly
                    import sqlite3
                    import os
                    db_path = os.getenv('SESSION_DB_PATH', './fuzzforge_sessions.db')
                    
                    if os.path.exists(db_path):
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        
                        # Search in events table
                        query = f"%{args}%"
                        cursor.execute(
                            "SELECT content FROM events WHERE content LIKE ? LIMIT 10",
                            (query,)
                        )
                        
                        rows = cursor.fetchall()
                        conn.close()
                        
                        if rows:
                            console.print(f"[green]Found {len(rows)} matches in SQLite sessions:[/green]\n")
                            for i, (content,) in enumerate(rows, 1):
                                # Parse JSON content
                                import json
                                try:
                                    data = json.loads(content)
                                    if 'parts' in data and data['parts']:
                                        text = data['parts'][0].get('text', '')[:150]
                                        role = data.get('role', 'unknown')
                                        console.print(f"{i}. [{role}]: {text}...")
                                except Exception:
                                    console.print(f"{i}. {content[:150]}...")
                        else:
                            console.print("[yellow]No matches found in SQLite either[/yellow]")
                    else:
                        console.print("[yellow]SQLite database not found[/yellow]")
                else:
                    console.print(f"[dim]Using {service_type} (not searchable)[/dim]")
            else:
                console.print("[yellow]No session history available[/yellow]")
    
    async def cmd_memory(self, args: str = "") -> None:
        """Inspect conversational memory and knowledge graph state."""
        raw_args = (args or "").strip()
        lower_args = raw_args.lower()

        if not raw_args or lower_args in {"status", "info"}:
            await self._show_memory_status()
            return

        if lower_args == "datasets":
            await self._show_dataset_summary()
            return

        if lower_args.startswith("search ") or lower_args.startswith("recall "):
            query = raw_args.split(" ", 1)[1].strip() if " " in raw_args else ""
            if not query:
                console.print("Usage: /memory search <query>")
                return
            await self.cmd_recall(query)
            return

        console.print("Usage: /memory [status|datasets|search <query>]")
        console.print("[dim]/memory search <query> is an alias for /recall <query>[/dim]")

    async def _sync_conversational_memory(self) -> None:
        """Ensure the ADK memory service ingests any completed sessions."""
        memory_service = getattr(self.agent.memory_manager, "memory_service", None)
        executor_sessions = getattr(self.agent.executor, "sessions", {})
        metadata_map = getattr(self.agent.executor, "session_metadata", {})

        if not memory_service or not executor_sessions:
            return

        for context_id, session in list(executor_sessions.items()):
            meta = metadata_map.get(context_id, {})
            if meta.get('memory_synced'):
                continue

            add_session = getattr(memory_service, "add_session_to_memory", None)
            if not callable(add_session):
                return

            try:
                await add_session(session)
                meta['memory_synced'] = True
                metadata_map[context_id] = meta
            except Exception as exc:  # pragma: no cover - defensive logging
                if os.getenv('FUZZFORGE_DEBUG', '0') == '1':
                    console.print(f"[yellow]Memory sync failed:[/yellow] {exc}")

    async def _show_memory_status(self) -> None:
        """Render conversational memory, session store, and knowledge graph status."""
        await self._sync_conversational_memory()

        status = self.agent.memory_manager.get_status()

        conversational = status.get("conversational_memory", {})
        conv_type = conversational.get("type", "unknown")
        conv_active = "yes" if conversational.get("active") else "no"
        conv_details = conversational.get("details", "")

        session_service = getattr(self.agent.executor, "session_service", None)
        session_service_name = type(session_service).__name__ if session_service else "Unavailable"

        session_lines = [
            f"[bold]Service:[/bold] {session_service_name}"
        ]

        session_count = None
        event_count = None
        db_path_display = None

        if session_service_name == "DatabaseSessionService":
            import sqlite3

            db_path = os.getenv('SESSION_DB_PATH', './fuzzforge_sessions.db')
            session_path = Path(db_path).expanduser().resolve()
            db_path_display = str(session_path)

            if session_path.exists():
                try:
                    with sqlite3.connect(session_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM sessions")
                        session_count = cursor.fetchone()[0]
                        cursor.execute("SELECT COUNT(*) FROM events")
                        event_count = cursor.fetchone()[0]
                except Exception as exc:
                    session_lines.append(f"[yellow]Warning:[/yellow] Unable to read session database ({exc})")
            else:
                session_lines.append("[yellow]SQLite session database not found yet[/yellow]")

        elif session_service_name == "InMemorySessionService":
            session_lines.append("[dim]Session data persists for the current process only[/dim]")

        if db_path_display:
            session_lines.append(f"[bold]Database:[/bold] {db_path_display}")
        if session_count is not None:
            session_lines.append(f"[bold]Sessions Recorded:[/bold] {session_count}")
        if event_count is not None:
            session_lines.append(f"[bold]Events Logged:[/bold] {event_count}")

        conv_lines = [
            f"[bold]Type:[/bold] {conv_type}",
            f"[bold]Active:[/bold] {conv_active}"
        ]
        if conv_details:
            conv_lines.append(f"[bold]Details:[/bold] {conv_details}")

        console.print(Panel("\n".join(conv_lines), title="Conversation Memory", border_style="medium_purple3"))
        console.print(Panel("\n".join(session_lines), title="Session Store", border_style="deep_sky_blue3"))

        # Knowledge graph section
        knowledge = status.get("knowledge_graph", {})
        kg_active = knowledge.get("active", False)
        kg_lines = [
            f"[bold]Active:[/bold] {'yes' if kg_active else 'no'}",
            f"[bold]Purpose:[/bold] {knowledge.get('purpose', 'N/A')}"
        ]

        cognee_data = None
        cognee_error = None
        try:
            project_config = ProjectConfigManager()
            cognee_data = project_config.get_cognee_config()
        except Exception as exc:  # pragma: no cover - defensive
            cognee_error = str(exc)

        if cognee_data:
            data_dir = cognee_data.get('data_directory')
            system_dir = cognee_data.get('system_directory')
            if data_dir:
                kg_lines.append(f"[bold]Data dir:[/bold] {data_dir}")
            if system_dir:
                kg_lines.append(f"[bold]System dir:[/bold] {system_dir}")
        elif cognee_error:
            kg_lines.append(f"[yellow]Config unavailable:[/yellow] {cognee_error}")

        dataset_summary = None
        if kg_active:
            try:
                integration = await self.agent.executor._get_knowledge_integration()
                if integration:
                    dataset_summary = await integration.list_datasets()
            except Exception as exc:  # pragma: no cover - defensive
                kg_lines.append(f"[yellow]Dataset listing failed:[/yellow] {exc}")

        if dataset_summary:
            if dataset_summary.get("error"):
                kg_lines.append(f"[yellow]Dataset listing failed:[/yellow] {dataset_summary['error']}")
            else:
                datasets = dataset_summary.get("datasets", [])
                total = dataset_summary.get("total_datasets")
                if total is not None:
                    kg_lines.append(f"[bold]Datasets:[/bold] {total}")
                if datasets:
                    preview = ", ".join(sorted(datasets)[:5])
                    if len(datasets) > 5:
                        preview += ", …"
                    kg_lines.append(f"[bold]Samples:[/bold] {preview}")
        else:
            kg_lines.append("[dim]Run `fuzzforge ingest` to populate the knowledge graph[/dim]")

        console.print(Panel("\n".join(kg_lines), title="Knowledge Graph", border_style="spring_green4"))
        console.print("\n[dim]Subcommands: /memory datasets | /memory search <query>[/dim]")

    async def _show_dataset_summary(self) -> None:
        """List datasets available in the Cognee knowledge graph."""
        try:
            integration = await self.agent.executor._get_knowledge_integration()
        except Exception as exc:
            console.print(f"[yellow]Knowledge graph unavailable:[/yellow] {exc}")
            return

        if not integration:
            console.print("[yellow]Knowledge graph is not initialised yet.[/yellow]")
            console.print("[dim]Run `fuzzforge ingest --path . --recursive` to create the project dataset.[/dim]")
            return

        with safe_status(get_dynamic_status('searching')):
            dataset_info = await integration.list_datasets()

        if dataset_info.get("error"):
            console.print(f"[red]{dataset_info['error']}[/red]")
            return

        datasets = dataset_info.get("datasets", [])
        if not datasets:
            console.print("[yellow]No datasets found.[/yellow]")
            console.print("[dim]Run `fuzzforge ingest` to populate the knowledge graph.[/dim]")
            return

        table = Table(title="Cognee Datasets", box=box.ROUNDED)
        table.add_column("Dataset", style="medium_purple3")
        table.add_column("Notes", style="dim")

        for name in sorted(datasets):
            note = ""
            if name.endswith("_codebase"):
                note = "primary project dataset"
            table.add_row(name, note)

        console.print(table)
        console.print(
            "[dim]Use knowledge graph prompts (e.g. `search project knowledge for \"topic\" using INSIGHTS`) to query these datasets.[/dim]"
        )
            
    async def cmd_artifacts(self, args: str = "") -> None:
        """List or show artifacts"""
        if args:
            # Show specific artifact
            artifacts = await self.agent.executor.get_artifacts(self.context_id)
            for artifact in artifacts:
                if artifact['id'] == args or args in artifact['id']:
                    console.print(Panel(
                        f"[bold]{artifact['title']}[/bold]\n"
                        f"Type: {artifact['type']} | Created: {artifact['created_at'][:19]}\n\n"
                        f"[code]{artifact['content']}[/code]",
                        title=f"Artifact: {artifact['id']}",
                        border_style="medium_purple3"
                    ))
                    return
            console.print(f"[yellow]Artifact {args} not found[/yellow]")
            return
        
        # List all artifacts
        artifacts = await self.agent.executor.get_artifacts(self.context_id)
        
        if not artifacts:
            console.print("No artifacts created yet")
            console.print("[dim]Artifacts are created when generating code, configs, or documents[/dim]")
            return
        
        table = Table(title="Artifacts", box=box.ROUNDED)
        table.add_column("ID", style="medium_purple3")
        table.add_column("Type", style="deep_sky_blue3")
        table.add_column("Title", style="plum3")
        table.add_column("Size", style="dim")
        table.add_column("Created", style="dim")
        
        for artifact in artifacts:
            size = f"{len(artifact['content'])} chars"
            created = artifact['created_at'][:19]  # Just date and time
            
        table.add_row(
            artifact['id'],
            artifact['type'],
            artifact['title'][:40] + "..." if len(artifact['title']) > 40 else artifact['title'],
            size,
            created
        )
        
        console.print(table)
        console.print("\n[dim]Use /artifacts <id> to view artifact content[/dim]")

    async def cmd_tasks(self, args: str = "") -> None:
        """List tasks or show details for a specific task."""
        store = getattr(self.agent.executor, "task_store", None)
        if not store or not hasattr(store, "tasks"):
            console.print("Task store not available")
            return

        task_id = args.strip()

        async with store.lock:
            tasks = dict(store.tasks)

        if not tasks:
            console.print("No tasks recorded yet")
            return

        if task_id:
            task = tasks.get(task_id)
            if not task:
                console.print(f"Task '{task_id}' not found")
                return

            state_str = task.status.state.value if hasattr(task.status.state, "value") else str(task.status.state)
            console.print(f"\n[bold]Task {task.id}[/bold]")
            console.print(f"Context: {task.context_id}")
            console.print(f"State: {state_str}")
            console.print(f"Timestamp: {task.status.timestamp}")
            if task.metadata:
                console.print("Metadata:")
                for key, value in task.metadata.items():
                    console.print(f"  • {key}: {value}")
            if task.history:
                console.print("History:")
                for entry in task.history[-5:]:
                    text = getattr(entry, "text", None)
                    if not text and hasattr(entry, "parts"):
                        text = " ".join(
                            getattr(part, "text", "") for part in getattr(entry, "parts", [])
                        )
                    console.print(f"  - {text}")
            return

        table = Table(title="FuzzForge Tasks", box=box.ROUNDED)
        table.add_column("ID", style="medium_purple3")
        table.add_column("State", style="white")
        table.add_column("Workflow", style="deep_sky_blue3")
        table.add_column("Updated", style="green")

        for task in tasks.values():
            state_value = task.status.state.value if hasattr(task.status.state, "value") else str(task.status.state)
            workflow = ""
            if task.metadata:
                workflow = task.metadata.get("workflow") or task.metadata.get("workflow_name") or ""
            timestamp = task.status.timestamp if task.status else ""
            table.add_row(task.id, state_value, workflow, timestamp)

        console.print(table)
        console.print("\n[dim]Use /tasks <id> to view task details[/dim]")
    
    async def cmd_sessions(self, args: str = "") -> None:
        """List active sessions"""
        sessions = self.agent.executor.sessions
        
        if not sessions:
            console.print("No active sessions")
            return
            
        table = Table(title="Active Sessions", box=box.ROUNDED)
        table.add_column("Context ID", style="medium_purple3")
        table.add_column("Session ID", style="deep_sky_blue3")
        table.add_column("User ID", style="plum3")
        table.add_column("State", style="dim")
        
        for context_id, session in sessions.items():
            # Get session info
            session_id = getattr(session, 'id', 'N/A')
            user_id = getattr(session, 'user_id', 'N/A')
            state = getattr(session, 'state', {})
            
            # Format state info
            agents_count = len(state.get('registered_agents', []))
            state_info = f"{agents_count} agents registered"
            
            table.add_row(
                context_id[:20] + "..." if len(context_id) > 20 else context_id,
                session_id[:20] + "..." if len(str(session_id)) > 20 else str(session_id),
                user_id,
                state_info
            )
            
        console.print(table)
        console.print(f"\n[dim]Current session: {self.context_id}[/dim]")
        
    async def cmd_skills(self, args: str = "") -> None:
        """Show FuzzForge skills"""
        card = self.agent.agent_card
        
        table = Table(title=f"{card.name} Skills", box=box.ROUNDED)
        table.add_column("Skill", style="medium_purple3")
        table.add_column("Description", style="white")
        table.add_column("Tags", style="deep_sky_blue3")
        
        for skill in card.skills:
            table.add_row(
                skill.name,
                skill.description,
                ", ".join(skill.tags[:3])
            )
            
        console.print(table)
        
    async def cmd_clear(self, args: str = "") -> None:
        """Clear screen"""
        console.clear()
        self.print_banner()

    async def cmd_sendfile(self, args: str) -> None:
        """Encode a local file as an artifact and route it to a registered agent."""
        tokens = shlex.split(args)
        if len(tokens) < 2:
            console.print("Usage: /sendfile <agent_name> <path> [message]")
            return

        agent_name = tokens[0]
        file_arg = tokens[1]
        note = " ".join(tokens[2:]).strip()

        file_path = Path(file_arg).expanduser()
        if not file_path.exists():
            console.print(f"[red]File not found:[/red] {file_path}")
            return

        session = self.agent.executor.sessions.get(self.context_id)
        if not session:
            console.print("[red]No active session available. Try sending a prompt first.[/red]")
            return

        console.print(f"[dim]Delegating {file_path.name} to {agent_name}...[/dim]")

        async def _delegate() -> None:
            try:
                response = await self.agent.executor.delegate_file_to_agent(
                    agent_name,
                    str(file_path),
                    note,
                    session=session,
                    context_id=self.context_id,
                )
                console.print(f"[{agent_name}]: {response}")
            except Exception as exc:
                console.print(f"[red]Failed to delegate file:[/red] {exc}")
            finally:
                self.background_tasks.discard(asyncio.current_task())

        task = asyncio.create_task(_delegate())
        self.background_tasks.add(task)
        console.print("[dim]Delegation in progress… you can continue working.[/dim]")

    async def cmd_quit(self, args: str = "") -> None:
        """Exit the CLI"""
        console.print("\n[green]Shutting down...[/green]")
        await self.agent.cleanup()
        if self.background_tasks:
            for task in list(self.background_tasks):
                task.cancel()
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        console.print("Goodbye!\n")
        sys.exit(0)

    async def process_command(self, text: str) -> bool:
        """Process slash commands"""
        if not text.startswith('/'):
            return False
            
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in self.commands:
            await self.commands[cmd](args)
            return True
            
        console.print(f"Unknown command: {cmd}")
        return True
        
    async def auto_register_agents(self):
        """Auto-register agents from config on startup"""
        agents_to_register = self.config_manager.get_registered_agents()
        
        if agents_to_register:
            console.print(f"\n[dim]Auto-registering {len(agents_to_register)} agents from config...[/dim]")
            
            for agent_config in agents_to_register:
                url = agent_config.get('url')
                name = agent_config.get('name', 'Unknown')
                
                if url:
                    try:
                        with safe_status(f"Registering {name}..."):
                            result = await self.agent.register_agent(url)
                        
                        if result["success"]:
                            console.print(f"  ✅ {name}: [green]Connected[/green]")
                        else:
                            console.print(f"  ⚠️  {name}: [yellow]Failed - {result.get('error', 'Unknown error')}[/yellow]")
                    except Exception as e:
                        console.print(f"  ⚠️  {name}: [yellow]Failed - {e}[/yellow]")
            
            console.print("")  # Empty line for spacing
    
    async def run(self):
        """Main CLI loop"""
        self.print_banner()
        
        # Auto-register agents from config
        await self.auto_register_agents()
        
        while not shutdown_requested:
            try:
                # Use standard input with non-deletable colored prompt
                prompt_symbol = get_prompt_symbol()
                try:
                    # Print colored prompt then use input() for non-deletable behavior
                    console.print(f"[medium_purple3]{prompt_symbol}[/medium_purple3] ", end="")
                    user_input = input().strip()
                except (EOFError, KeyboardInterrupt):
                    raise
                
                if not user_input:
                    continue
                    
                # Check for commands
                if await self.process_command(user_input):
                    continue
                    
                # Process message
                with safe_status(get_dynamic_status('thinking')):
                    response = await self.agent.process_message(user_input, self.context_id)
                    
                # Display response
                console.print(f"\n{response}\n")
                    
            except KeyboardInterrupt:
                await self.cmd_quit()
                
            except EOFError:
                await self.cmd_quit()
                
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if os.getenv('FUZZFORGE_DEBUG') == '1':
                    console.print_exception()
                console.print("")
        
        await self.agent.cleanup()


def main():
    """Main entry point"""
    try:
        cli = FuzzForgeCLI()
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        if os.getenv('FUZZFORGE_DEBUG') == '1':
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
