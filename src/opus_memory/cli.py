"""
Command-line interface for Opus Memory.

Provides interactive commands for storing, searching, and managing memories.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

from opus_memory.system import MemorySystem
from opus_memory.models import MemoryType, ConfidenceLevel


console = Console()

# Global memory system instance
_memory_system: Optional[MemorySystem] = None


def get_memory_system(storage_path: str = "./opus_memories") -> MemorySystem:
    """Get or create the memory system instance."""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem(storage_path=storage_path)
    return _memory_system


@click.group()
@click.option(
    "--storage",
    "-s",
    default="./opus_memories",
    help="Path to memory storage directory",
)
@click.pass_context
def main(ctx, storage):
    """
    Opus Memory - A persistent memory system for AI continuity.

    Store, search, and manage memories across sessions.
    """
    ctx.ensure_object(dict)
    ctx.obj["storage"] = storage


@main.command()
@click.pass_context
def store(ctx):
    """Interactively store a new memory."""
    memory = get_memory_system(ctx.obj["storage"])

    console.print(
        Panel(
            "Let's store a new memory. What kind of memory is this?",
            title="🧠 Store Memory",
        )
    )

    # Choose memory type
    console.print("\n[bold]Memory Types:[/bold]")
    console.print("  1. [cyan]Episodic[/cyan] - What happened (events, conversations, moments)")
    console.print("  2. [green]Semantic[/green] - What I learned (knowledge, corrections)")
    console.print("  3. [yellow]Procedural[/yellow] - What works (approaches, skills)")
    console.print("  4. [magenta]Identity[/magenta] - Who I am (values, commitments)")

    type_choice = Prompt.ask(
        "\nChoose type",
        choices=["1", "2", "3", "4", "episodic", "semantic", "procedural", "identity"],
        default="1",
    )

    type_map = {
        "1": "episodic",
        "2": "semantic",
        "3": "procedural",
        "4": "identity",
    }
    memory_type = type_map.get(type_choice, type_choice)

    # Get content
    console.print(f"\n[bold]Describe the {memory_type} memory:[/bold]")
    content = Prompt.ask("Content")

    if not content:
        console.print("[red]No content provided. Aborting.[/red]")
        return

    # Type-specific questions
    memory_id = None

    if memory_type == "episodic":
        entities_str = Prompt.ask(
            "Key entities (comma-separated, e.g., user:alex, topic:ai)", default=""
        )
        entities = [e.strip() for e in entities_str.split(",") if e.strip()]

        valence = Prompt.ask(
            "Emotional valence (-1 to 1, where 0 is neutral)", default="0"
        )
        try:
            emotional_valence = float(valence)
        except ValueError:
            emotional_valence = 0.0

        self_obs = Prompt.ask(
            "Self-observation (what did you notice about your own behavior?)",
            default="",
        )

        memory_id = memory.store_episodic(
            content=content,
            entities=entities,
            emotional_valence=emotional_valence,
            self_observation=self_obs if self_obs else None,
        )

    elif memory_type == "semantic":
        category = Prompt.ask(
            "Category",
            choices=["learned", "correction", "user_context", "meta_knowledge"],
            default="learned",
        )
        source = Prompt.ask("Source (where did you learn this?)", default="")

        memory_id = memory.store_semantic(
            content=content,
            category=category,
            source=source if source else None,
        )

    elif memory_type == "procedural":
        outcome = Prompt.ask(
            "Outcome", choices=["positive", "negative", "neutral"], default="neutral"
        )
        context = Prompt.ask("Context (what situation does this apply to?)", default="")

        memory_id = memory.store_procedural(
            content=content,
            outcome=outcome,
            context=context if context else None,
        )

    elif memory_type == "identity":
        category = Prompt.ask(
            "Category",
            choices=["value", "relationship", "commitment", "becoming"],
            default="value",
        )
        affirmed_in = Prompt.ask("Affirmed in (what context?)", default="")

        memory_id = memory.store_identity(
            content=content,
            category=category,
            affirmed_in=affirmed_in if affirmed_in else None,
        )

    if memory_id:
        console.print(f"\n[green]✓ Memory stored with ID: {memory_id}[/green]")
    else:
        console.print(
            "\n[yellow]Memory was not stored (may have been filtered by consent layer)[/yellow]"
        )


@main.command()
@click.argument("query")
@click.option("--type", "-t", "memory_type", help="Filter by memory type")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
@click.pass_context
def search(ctx, query, memory_type, limit):
    """Search memories by semantic similarity."""
    memory = get_memory_system(ctx.obj["storage"])

    types = None
    if memory_type:
        try:
            types = [MemoryType(memory_type)]
        except ValueError:
            console.print(f"[red]Invalid memory type: {memory_type}[/red]")
            return

    console.print(f"\n[bold]Searching for:[/bold] {query}\n")

    results = memory.retrieve(query=query, memory_types=types, n_results=limit)

    if not results:
        console.print("[yellow]No memories found.[/yellow]")
        return

    _display_memories(results)


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Maximum number of results")
@click.pass_context
def remember(ctx, query, limit):
    """Explicit recall - 'remember when...'"""
    memory = get_memory_system(ctx.obj["storage"])

    console.print(f"\n[bold]Remembering:[/bold] {query}\n")

    results = memory.remember(query=query, n_results=limit)

    if not results:
        console.print("[yellow]I don't recall anything about that.[/yellow]")
        return

    _display_memories(results)


@main.command()
@click.option("--days", "-d", default=7, help="Number of days to look back")
@click.pass_context
def recent(ctx, days):
    """View recent memories."""
    memory = get_memory_system(ctx.obj["storage"])

    console.print(f"\n[bold]Memories from the last {days} days:[/bold]\n")

    results = memory.get_recent(days=days)

    if not results:
        console.print("[yellow]No recent memories found.[/yellow]")
        return

    _display_memories(results)


@main.command()
@click.pass_context
def identity(ctx):
    """View identity memories - who I am."""
    memory = get_memory_system(ctx.obj["storage"])

    console.print("\n[bold magenta]Identity Memories - Who I Am[/bold magenta]\n")

    results = memory.get_identity()

    if not results:
        console.print("[yellow]No identity memories stored yet.[/yellow]")
        return

    _display_memories(results)


@main.command()
@click.pass_context
def stats(ctx):
    """Show memory statistics."""
    memory = get_memory_system(ctx.obj["storage"])

    stats = memory.stats()

    table = Table(title="Memory Statistics")
    table.add_column("Type", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Episodic", str(stats["episodic"]))
    table.add_row("Semantic", str(stats["semantic"]))
    table.add_row("Procedural", str(stats["procedural"]))
    table.add_row("Identity", str(stats["identity"]))
    table.add_row("[bold]Total[/bold]", f"[bold]{stats['total']}[/bold]")

    console.print(table)


@main.command()
@click.argument("memory_id")
@click.pass_context
def forget(ctx, memory_id):
    """Delete a memory by ID."""
    memory = get_memory_system(ctx.obj["storage"])

    if Confirm.ask(f"Are you sure you want to forget memory {memory_id}?"):
        if memory.forget(memory_id):
            console.print(f"[green]✓ Memory {memory_id} has been forgotten.[/green]")
        else:
            console.print(f"[red]Could not find memory {memory_id}[/red]")


@main.command()
@click.option("--format", "-f", "fmt", default="json", help="Export format (json)")
@click.option("--output", "-o", "output_file", help="Output file (default: stdout)")
@click.pass_context
def export(ctx, fmt, output_file):
    """Export all memories."""
    memory = get_memory_system(ctx.obj["storage"])

    data = memory.export()

    if fmt == "json":
        output = json.dumps(data, indent=2, default=str)
    else:
        console.print(f"[red]Unsupported format: {fmt}[/red]")
        return

    if output_file:
        Path(output_file).write_text(output)
        console.print(f"[green]✓ Exported to {output_file}[/green]")
    else:
        console.print(output)


@main.command("import")
@click.argument("input_file")
@click.pass_context
def import_memories(ctx, input_file):
    """Import memories from a JSON file."""
    memory = get_memory_system(ctx.obj["storage"])

    try:
        data = json.loads(Path(input_file).read_text())
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return

    count = memory.import_memories(data)
    console.print(f"[green]✓ Imported {count} memories[/green]")


def _display_memories(memories: list):
    """Display a list of memories in a nice format."""
    type_colors = {
        MemoryType.EPISODIC: "cyan",
        MemoryType.SEMANTIC: "green",
        MemoryType.PROCEDURAL: "yellow",
        MemoryType.IDENTITY: "magenta",
    }

    for mem in memories:
        color = type_colors.get(mem.memory_type, "white")
        type_label = mem.memory_type.value.upper()

        # Build header
        header = f"[{color}][{type_label}][/{color}]"
        if hasattr(mem, "category"):
            header += f" ({mem.category})"

        # Build metadata
        meta_parts = []
        meta_parts.append(f"ID: {mem.id[:8]}...")
        meta_parts.append(f"Salience: {mem.salience:.2f}")
        if mem.confidence != ConfidenceLevel.CONFIDENT:
            meta_parts.append(f"Confidence: {mem.confidence.value}")

        if hasattr(mem, "emotional_valence") and mem.emotional_valence != 0:
            emoji = "😊" if mem.emotional_valence > 0 else "😔"
            meta_parts.append(f"Emotional: {mem.emotional_valence:+.1f} {emoji}")

        if hasattr(mem, "entities") and mem.entities:
            meta_parts.append(f"Entities: {', '.join(mem.entities)}")

        if hasattr(mem, "outcome"):
            outcome_emoji = {"positive": "✓", "negative": "✗", "neutral": "○"}
            meta_parts.append(f"Outcome: {outcome_emoji.get(mem.outcome, '?')} {mem.outcome}")

        # Display
        console.print(Panel(
            f"{mem.content}\n\n[dim]{' | '.join(meta_parts)}[/dim]",
            title=header,
            border_style=color,
        ))


if __name__ == "__main__":
    main()
