"""
Main CLI entry point for Debai.

Provides a comprehensive command-line interface for managing AI agents,
models, tasks, and system generation.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.tree import Tree
from rich import box

from debai import __version__
from debai.core.agent import (
    Agent, AgentConfig, AgentManager, AgentType, AgentCapability,
    get_agent_template, list_agent_templates,
)
from debai.core.model import (
    Model, ModelConfig, ModelManager,
    get_recommended_model, list_recommended_models,
)
from debai.core.task import (
    Task, TaskConfig, TaskManager, TaskType, TaskPriority,
    get_task_template, list_task_templates,
)
from debai.core.system import SystemInfo, ResourceMonitor, check_dependencies, get_docker_status

# Set up console and logging
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def print_banner() -> None:
    """Print the Debai banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     ██████╗ ███████╗██████╗  █████╗ ██╗                      ║
    ║     ██╔══██╗██╔════╝██╔══██╗██╔══██╗██║                      ║
    ║     ██║  ██║█████╗  ██████╔╝███████║██║                      ║
    ║     ██║  ██║██╔══╝  ██╔══██╗██╔══██║██║                      ║
    ║     ██████╔╝███████╗██████╔╝██║  ██║██║                      ║
    ║     ╚═════╝ ╚══════╝╚═════╝ ╚═╝  ╚═╝╚═╝                      ║
    ║                                                              ║
    ║     AI Agent Management System for GNU/Linux                 ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


# ============================================================================
# Main CLI Group
# ============================================================================

@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-c", "--config", type=click.Path(), help="Configuration file path")
@click.version_option(version=__version__, prog_name="debai")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Optional[str]) -> None:
    """
    Debai - AI Agent Management System for GNU/Linux
    
    Manage AI agents that automate system tasks like package updates,
    configuration management, and resource monitoring.
    
    Use 'debai COMMAND --help' for more information on a specific command.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config
    setup_logging(verbose)


# ============================================================================
# Status Command
# ============================================================================

@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show system and Debai status."""
    print_banner()
    
    # System information
    console.print("\n[bold cyan]📊 System Information[/bold cyan]\n")
    
    info = SystemInfo.get_summary()
    
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Property", style="bold")
    table.add_column("Value")
    
    table.add_row("Hostname", info["hostname"])
    table.add_row("OS", f"{info['os']['system']} {info['os']['release']}")
    table.add_row("Distribution", f"{info['distro']['name']} {info['distro']['version']}")
    table.add_row("CPU", info["cpu"]["model"][:50] if info["cpu"]["model"] else "Unknown")
    table.add_row("Cores", f"{info['cpu']['cores_physical']} physical / {info['cpu']['cores_logical']} logical")
    table.add_row("CPU Usage", f"{info['cpu']['usage_percent']:.1f}%")
    table.add_row("Memory", f"{info['memory']['percent_used']:.1f}% used")
    table.add_row("Uptime", info["uptime"])
    table.add_row("Load", f"{info['load_average'][0]:.2f}, {info['load_average'][1]:.2f}, {info['load_average'][2]:.2f}")
    
    console.print(table)
    
    # Dependencies
    console.print("\n[bold cyan]🔧 Dependencies[/bold cyan]\n")
    
    deps = check_dependencies()
    dep_table = Table(box=box.ROUNDED, show_header=True, padding=(0, 2))
    dep_table.add_column("Dependency")
    dep_table.add_column("Status")
    
    for dep, available in deps.items():
        status_icon = "[green]✓ Available[/green]" if available else "[red]✗ Missing[/red]"
        dep_table.add_row(dep, status_icon)
    
    console.print(dep_table)
    
    # Docker status
    docker = get_docker_status()
    if docker["installed"]:
        console.print("\n[bold cyan]🐳 Docker Status[/bold cyan]\n")
        docker_table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
        docker_table.add_column("Property", style="bold")
        docker_table.add_column("Value")
        
        docker_table.add_row("Version", docker["version"])
        docker_table.add_row("Running", "[green]Yes[/green]" if docker["running"] else "[red]No[/red]")
        docker_table.add_row("Containers", str(docker["containers"]))
        docker_table.add_row("Images", str(docker["images"]))
        
        console.print(docker_table)


# ============================================================================
# Agent Commands
# ============================================================================

@cli.group()
def agent() -> None:
    """Manage AI agents."""
    pass


@agent.command("list")
@click.option("-s", "--status", type=click.Choice(["running", "stopped", "all"]), default="all")
@click.pass_context
def agent_list(ctx: click.Context, status: str) -> None:
    """List all agents."""
    manager = AgentManager()
    manager.load_agents()
    
    agents = manager.list_agents()
    
    if not agents:
        console.print("[yellow]No agents found. Create one with 'debai agent create'[/yellow]")
        return
    
    table = Table(
        title="[bold]AI Agents[/bold]",
        box=box.ROUNDED,
        show_header=True,
        padding=(0, 1),
    )
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Model")
    table.add_column("Interactive")
    
    for agent in agents:
        status_icon = {
            "stopped": "[dim]● Stopped[/dim]",
            "running": "[green]● Running[/green]",
            "error": "[red]● Error[/red]",
            "waiting": "[yellow]● Waiting[/yellow]",
        }.get(agent.status.value, agent.status.value)
        
        interactive = "✓" if agent.config.interactive else "✗"
        
        table.add_row(
            agent.id,
            agent.name,
            agent.config.agent_type,
            status_icon,
            agent.config.model_id,
            interactive,
        )
    
    console.print(table)


@agent.command("create")
@click.option("-n", "--name", prompt="Agent name", help="Name for the agent")
@click.option("-t", "--type", "agent_type", 
              type=click.Choice([t.value for t in AgentType]),
              default="custom", help="Agent type")
@click.option("-m", "--model", default="llama3.2:3b", help="Model to use")
@click.option("--template", help="Use a predefined template")
@click.option("--interactive/--no-interactive", default=True, help="Allow user interaction")
@click.pass_context
def agent_create(
    ctx: click.Context,
    name: str,
    agent_type: str,
    model: str,
    template: Optional[str],
    interactive: bool,
) -> None:
    """Create a new agent."""
    if template:
        config = get_agent_template(template)
        if not config:
            console.print(f"[red]Template '{template}' not found[/red]")
            console.print(f"Available templates: {', '.join(list_agent_templates())}")
            return
        config.name = name
        config.model_id = model
    else:
        config = AgentConfig(
            name=name,
            agent_type=AgentType(agent_type),
            model_id=model,
            interactive=interactive,
        )
    
    manager = AgentManager()
    
    async def create():
        agent = await manager.create_agent(config)
        return agent
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Creating agent...", total=None)
        agent = asyncio.run(create())
    
    console.print(f"\n[green]✓ Agent created successfully![/green]")
    console.print(f"  ID: [cyan]{agent.id}[/cyan]")
    console.print(f"  Name: {agent.name}")
    console.print(f"  Type: {agent.config.agent_type}")
    console.print(f"  Model: {agent.config.model_id}")
    console.print(f"\nStart with: [bold]debai agent start {agent.id}[/bold]")


@agent.command("start")
@click.argument("agent_id")
@click.pass_context
def agent_start(ctx: click.Context, agent_id: str) -> None:
    """Start an agent."""
    manager = AgentManager()
    manager.load_agents()
    
    agent = manager.get_agent(agent_id)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        return
    
    async def start():
        return await agent.start()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Starting agent '{agent.name}'...", total=None)
        success = asyncio.run(start())
    
    if success:
        console.print(f"[green]✓ Agent '{agent.name}' started[/green]")
    else:
        console.print(f"[red]✗ Failed to start agent '{agent.name}'[/red]")


@agent.command("stop")
@click.argument("agent_id")
@click.pass_context
def agent_stop(ctx: click.Context, agent_id: str) -> None:
    """Stop an agent."""
    manager = AgentManager()
    manager.load_agents()
    
    agent = manager.get_agent(agent_id)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        return
    
    async def stop():
        return await agent.stop()
    
    success = asyncio.run(stop())
    
    if success:
        console.print(f"[green]✓ Agent '{agent.name}' stopped[/green]")
    else:
        console.print(f"[red]✗ Failed to stop agent '{agent.name}'[/red]")


@agent.command("delete")
@click.argument("agent_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def agent_delete(ctx: click.Context, agent_id: str, force: bool) -> None:
    """Delete an agent."""
    manager = AgentManager()
    manager.load_agents()
    
    agent = manager.get_agent(agent_id)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        return
    
    if not force:
        if not Confirm.ask(f"Delete agent '{agent.name}'?"):
            return
    
    async def delete():
        return await manager.delete_agent(agent_id)
    
    success = asyncio.run(delete())
    
    if success:
        console.print(f"[green]✓ Agent '{agent.name}' deleted[/green]")
    else:
        console.print(f"[red]✗ Failed to delete agent[/red]")


@agent.command("chat")
@click.argument("agent_id")
@click.pass_context
def agent_chat(ctx: click.Context, agent_id: str) -> None:
    """Start an interactive chat session with an agent."""
    manager = AgentManager()
    manager.load_agents()
    
    agent = manager.get_agent(agent_id)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        return
    
    console.print(Panel(
        f"[bold]Chat with {agent.name}[/bold]\n\n"
        f"Type your message and press Enter.\n"
        f"Type 'exit' or 'quit' to end the session.",
        title="Agent Chat",
        border_style="cyan",
    ))
    
    async def chat_session():
        await agent.start()
        
        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                
                if user_input.lower() in ("exit", "quit", "q"):
                    break
                
                response = await agent.send_message(user_input)
                if response:
                    console.print(f"\n[bold green]{agent.name}[/bold green]: {response.content}")
                else:
                    console.print("[yellow]No response from agent[/yellow]")
            
            except KeyboardInterrupt:
                break
        
        await agent.stop()
    
    asyncio.run(chat_session())
    console.print("\n[dim]Chat session ended[/dim]")


@agent.command("templates")
def agent_templates() -> None:
    """List available agent templates."""
    templates = list_agent_templates()
    
    table = Table(
        title="[bold]Agent Templates[/bold]",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Template")
    table.add_column("Description")
    table.add_column("Type")
    
    for name in templates:
        config = get_agent_template(name)
        if config:
            table.add_row(name, config.description, config.agent_type)
    
    console.print(table)
    console.print("\nUse with: [bold]debai agent create --template <name>[/bold]")


# ============================================================================
# Model Commands
# ============================================================================

@cli.group()
def model() -> None:
    """Manage AI models."""
    pass


@model.command("list")
@click.pass_context
def model_list(ctx: click.Context) -> None:
    """List available models."""
    manager = ModelManager()
    manager.load_models()
    
    # Also try to discover from Docker Model
    async def discover():
        return await manager.discover_models()
    
    discovered = asyncio.run(discover())
    
    models = manager.list_models()
    
    if not models and not discovered:
        console.print("[yellow]No models found.[/yellow]")
        console.print("Pull a model with: [bold]debai model pull <model-id>[/bold]")
        return
    
    table = Table(
        title="[bold]AI Models[/bold]",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Size")
    
    for m in models:
        status_icon = {
            "ready": "[green]● Ready[/green]",
            "loaded": "[green]● Loaded[/green]",
            "pulling": "[yellow]● Pulling[/yellow]",
            "not_pulled": "[dim]● Not Pulled[/dim]",
            "error": "[red]● Error[/red]",
        }.get(m.status.value, m.status.value)
        
        size = f"{m.config.size_bytes / (1024**3):.1f} GB" if m.config.size_bytes else "-"
        table.add_row(m.id, m.name, status_icon, size)
    
    console.print(table)


@model.command("pull")
@click.argument("model_id")
@click.pass_context
def model_pull(ctx: click.Context, model_id: str) -> None:
    """Pull a model from Docker Model Runner."""
    manager = ModelManager()
    
    config = ModelConfig(id=model_id, name=model_id)
    
    async def pull():
        m = await manager.add_model(config)
        return await m.pull()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Pulling model '{model_id}'...", total=None)
        success = asyncio.run(pull())
    
    if success:
        console.print(f"[green]✓ Model '{model_id}' pulled successfully[/green]")
    else:
        console.print(f"[red]✗ Failed to pull model '{model_id}'[/red]")


@model.command("remove")
@click.argument("model_id")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_context
def model_remove(ctx: click.Context, model_id: str, force: bool) -> None:
    """Remove a model."""
    if not force:
        if not Confirm.ask(f"Remove model '{model_id}'?"):
            return
    
    manager = ModelManager()
    manager.load_models()
    
    async def remove():
        return await manager.remove_model(model_id)
    
    success = asyncio.run(remove())
    
    if success:
        console.print(f"[green]✓ Model '{model_id}' removed[/green]")
    else:
        console.print(f"[red]✗ Failed to remove model '{model_id}'[/red]")


@model.command("recommended")
def model_recommended() -> None:
    """Show recommended models for different use cases."""
    table = Table(
        title="[bold]Recommended Models[/bold]",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Use Case")
    table.add_column("Model")
    table.add_column("Description")
    table.add_column("Parameters")
    
    for name in list_recommended_models():
        config = get_recommended_model(name)
        if config:
            table.add_row(
                name,
                config.id,
                config.description,
                config.parameter_count,
            )
    
    console.print(table)
    console.print("\nPull with: [bold]debai model pull <model-id>[/bold]")


# ============================================================================
# Task Commands
# ============================================================================

@cli.group()
def task() -> None:
    """Manage automated tasks."""
    pass


@task.command("list")
@click.option("-s", "--status", type=click.Choice(["pending", "running", "completed", "failed", "all"]), default="all")
@click.pass_context
def task_list(ctx: click.Context, status: str) -> None:
    """List all tasks."""
    manager = TaskManager()
    manager.load_tasks()
    
    tasks = manager.list_tasks()
    
    if not tasks:
        console.print("[yellow]No tasks found. Create one with 'debai task create'[/yellow]")
        return
    
    table = Table(
        title="[bold]Tasks[/bold]",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Priority")
    table.add_column("Status")
    
    for t in tasks:
        status_icon = {
            "pending": "[dim]○ Pending[/dim]",
            "scheduled": "[blue]◐ Scheduled[/blue]",
            "running": "[yellow]● Running[/yellow]",
            "completed": "[green]✓ Completed[/green]",
            "failed": "[red]✗ Failed[/red]",
            "cancelled": "[dim]✗ Cancelled[/dim]",
        }.get(t.status.value, t.status.value)
        
        priority_style = {
            "low": "[dim]Low[/dim]",
            "normal": "Normal",
            "high": "[yellow]High[/yellow]",
            "critical": "[red bold]Critical[/red bold]",
        }.get(t.config.priority, t.config.priority)
        
        table.add_row(
            t.id,
            t.name,
            t.config.task_type,
            priority_style,
            status_icon,
        )
    
    console.print(table)


@task.command("create")
@click.option("-n", "--name", prompt="Task name", help="Name for the task")
@click.option("-c", "--command", prompt="Command to run", help="Shell command to execute")
@click.option("-p", "--priority", 
              type=click.Choice(["low", "normal", "high", "critical"]),
              default="normal", help="Task priority")
@click.option("--template", help="Use a predefined template")
@click.pass_context
def task_create(
    ctx: click.Context,
    name: str,
    command: str,
    priority: str,
    template: Optional[str],
) -> None:
    """Create a new task."""
    if template:
        config = get_task_template(template)
        if not config:
            console.print(f"[red]Template '{template}' not found[/red]")
            console.print(f"Available templates: {', '.join(list_task_templates())}")
            return
        config.name = name
    else:
        config = TaskConfig(
            name=name,
            command=command,
            priority=TaskPriority(priority),
        )
    
    manager = TaskManager()
    
    async def create():
        return await manager.create_task(config)
    
    task = asyncio.run(create())
    
    console.print(f"\n[green]✓ Task created successfully![/green]")
    console.print(f"  ID: [cyan]{task.id}[/cyan]")
    console.print(f"  Name: {task.name}")
    console.print(f"\nRun with: [bold]debai task run {task.id}[/bold]")


@task.command("run")
@click.argument("task_id")
@click.pass_context
def task_run(ctx: click.Context, task_id: str) -> None:
    """Run a task."""
    manager = TaskManager()
    manager.load_tasks()
    
    t = manager.get_task(task_id)
    if not t:
        console.print(f"[red]Task '{task_id}' not found[/red]")
        return
    
    async def run():
        return await t.execute()
    
    console.print(f"[bold]Running task: {t.name}[/bold]\n")
    
    result = asyncio.run(run())
    
    if result.success:
        console.print(f"[green]✓ Task completed successfully[/green]")
        if result.stdout:
            console.print(Panel(result.stdout, title="Output", border_style="green"))
    else:
        console.print(f"[red]✗ Task failed[/red]")
        if result.stderr:
            console.print(Panel(result.stderr, title="Error", border_style="red"))
    
    console.print(f"\n[dim]Duration: {result.duration_seconds:.2f}s[/dim]")


@task.command("templates")
def task_templates() -> None:
    """List available task templates."""
    templates = list_task_templates()
    
    table = Table(
        title="[bold]Task Templates[/bold]",
        box=box.ROUNDED,
        show_header=True,
    )
    table.add_column("Template")
    table.add_column("Description")
    table.add_column("Priority")
    
    for name in templates:
        config = get_task_template(name)
        if config:
            table.add_row(name, config.description, config.priority)
    
    console.print(table)
    console.print("\nUse with: [bold]debai task create --template <name>[/bold]")


# ============================================================================
# Generate Commands
# ============================================================================

@cli.group()
def generate() -> None:
    """Generate distribution images and configurations."""
    pass


@generate.command("iso")
@click.option("-o", "--output", default="debai.iso", help="Output ISO file path")
@click.option("--base", default="debian", help="Base distribution")
@click.option("--include-agents", is_flag=True, help="Include configured agents")
@click.pass_context
def generate_iso(ctx: click.Context, output: str, base: str, include_agents: bool) -> None:
    """Generate a bootable ISO image."""
    from debai.generators.iso import ISOGenerator
    
    console.print(Panel(
        f"[bold]Generating ISO Image[/bold]\n\n"
        f"Output: {output}\n"
        f"Base: {base}\n"
        f"Include agents: {include_agents}",
        title="ISO Generation",
        border_style="cyan",
    ))
    
    generator = ISOGenerator(
        output_path=Path(output),
        base_distro=base,
        include_agents=include_agents,
    )
    
    async def gen():
        return await generator.generate()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating ISO...", total=None)
        result = asyncio.run(gen())
    
    if result["success"]:
        console.print(f"\n[green]✓ ISO generated: {output}[/green]")
        console.print(f"  Size: {result['size_mb']:.1f} MB")
    else:
        console.print(f"\n[red]✗ Failed to generate ISO[/red]")
        if result.get("error"):
            console.print(f"  Error: {result['error']}")


@generate.command("qcow2")
@click.option("-o", "--output", default="debai.qcow2", help="Output QCOW2 file path")
@click.option("--size", default="20G", help="Disk size")
@click.option("--base", default="debian", help="Base distribution")
@click.pass_context
def generate_qcow2(ctx: click.Context, output: str, size: str, base: str) -> None:
    """Generate a QCOW2 image for QEMU."""
    from debai.generators.qcow2 import QCOW2Generator
    
    console.print(Panel(
        f"[bold]Generating QCOW2 Image[/bold]\n\n"
        f"Output: {output}\n"
        f"Size: {size}\n"
        f"Base: {base}",
        title="QCOW2 Generation",
        border_style="cyan",
    ))
    
    generator = QCOW2Generator(
        output_path=Path(output),
        disk_size=size,
        base_distro=base,
    )
    
    async def gen():
        return await generator.generate()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating QCOW2...", total=None)
        result = asyncio.run(gen())
    
    if result["success"]:
        console.print(f"\n[green]✓ QCOW2 generated: {output}[/green]")
        console.print(f"  Size: {result['size_mb']:.1f} MB")
    else:
        console.print(f"\n[red]✗ Failed to generate QCOW2[/red]")
        if result.get("error"):
            console.print(f"  Error: {result['error']}")


@generate.command("compose")
@click.option("-o", "--output", default="docker-compose.yml", help="Output file path")
@click.option("--include-gui", is_flag=True, help="Include GUI service")
@click.pass_context
def generate_compose(ctx: click.Context, output: str, include_gui: bool) -> None:
    """Generate a Docker Compose configuration."""
    from debai.generators.compose import ComposeGenerator
    
    generator = ComposeGenerator(
        output_path=Path(output),
        include_gui=include_gui,
    )
    
    result = generator.generate()
    
    if result["success"]:
        console.print(f"[green]✓ Docker Compose generated: {output}[/green]")
        console.print("\nStart with: [bold]docker compose up -d[/bold]")
    else:
        console.print(f"[red]✗ Failed to generate Docker Compose[/red]")


# ============================================================================
# Init Command
# ============================================================================

@cli.command()
@click.option("--full", is_flag=True, help="Full initialization with model pull")
@click.pass_context
def init(ctx: click.Context, full: bool) -> None:
    """Initialize Debai environment."""
    print_banner()
    
    console.print("\n[bold cyan]🚀 Initializing Debai...[/bold cyan]\n")
    
    # Create configuration directories
    config_dir = Path.home() / ".config" / "debai"
    dirs = [
        config_dir,
        config_dir / "agents",
        config_dir / "models",
        config_dir / "tasks",
        Path.home() / ".local" / "share" / "debai",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        console.print(f"  [green]✓[/green] Created {d}")
    
    # Check dependencies
    console.print("\n[bold]Checking dependencies...[/bold]\n")
    deps = check_dependencies()
    
    missing = [d for d, available in deps.items() if not available]
    if missing:
        console.print(f"[yellow]⚠ Missing dependencies: {', '.join(missing)}[/yellow]")
        console.print("\nInstall with your package manager:")
        console.print("  [dim]sudo apt install docker.io qemu-utils genisoimage[/dim]")
    else:
        console.print("  [green]✓[/green] All dependencies available")
    
    if full:
        # Pull recommended model
        console.print("\n[bold]Pulling recommended model...[/bold]\n")
        manager = ModelManager()
        config = get_recommended_model("general")
        if config:
            async def pull():
                m = await manager.add_model(config)
                return await m.pull()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(f"Pulling {config.id}...", total=None)
                asyncio.run(pull())
    
    console.print("\n[bold green]✓ Debai initialized successfully![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Create an agent: [bold]debai agent create[/bold]")
    console.print("  2. Pull a model: [bold]debai model pull llama3.2:3b[/bold]")
    console.print("  3. Start the GUI: [bold]debai-gui[/bold]")


# ============================================================================
# Monitor Command
# ============================================================================

@cli.command()
@click.option("-i", "--interval", default=2.0, help="Update interval in seconds")
@click.pass_context
def monitor(ctx: click.Context, interval: float) -> None:
    """Monitor system resources in real-time."""
    from rich.live import Live
    from rich.layout import Layout
    
    console.print("[bold]Starting resource monitor...[/bold]")
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")
    
    monitor = ResourceMonitor(interval_seconds=interval)
    
    def create_display() -> Table:
        snapshot = monitor.get_latest()
        if not snapshot:
            return Table()
        
        table = Table(box=box.ROUNDED, show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        
        table.add_row("CPU", f"{snapshot['cpu_percent']:.1f}%")
        table.add_row("Memory", f"{snapshot['memory_percent']:.1f}%")
        table.add_row("Load (1m)", f"{snapshot['load_1min']:.2f}")
        table.add_row("Load (5m)", f"{snapshot['load_5min']:.2f}")
        table.add_row("Load (15m)", f"{snapshot['load_15min']:.2f}")
        
        return table
    
    async def run_monitor():
        await monitor.start()
        
        try:
            with Live(create_display(), console=console, refresh_per_second=1) as live:
                while True:
                    await asyncio.sleep(interval)
                    live.update(create_display())
        except KeyboardInterrupt:
            pass
        finally:
            await monitor.stop()
    
    asyncio.run(run_monitor())


# ============================================================================
# Entry Point
# ============================================================================

def main() -> None:
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
