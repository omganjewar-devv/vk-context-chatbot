#!/usr/bin/env python3
"""
Interactive Command Line Interface (CLI) for Context-Aware Multi-Turn Chatbot.
Provides a terminal experience with context inspection, strategy toggling, and multi-turn persistence.
"""

import sys
import uuid
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt

from app.config import settings
from app.core.memory import conversation_manager
from app.core.system_prompt import get_default_system_prompt
from app.core.llm_client import get_llm_client, LLMException

console = Console()


def print_banner():
    provider_name = settings.llm_provider.upper()
    model_name = settings.gemini_model if settings.llm_provider == "gemini" else settings.openai_model
    has_key = settings.has_valid_api_key()
    mode_text = f"[green]Cloud API ({provider_name} - {model_name})[/green]" if has_key else "[yellow]Simulation Mode (No API key set in .env)[/yellow]"

    banner_text = f"""[bold cyan]Atlas AI[/bold cyan] - Context-Aware Multi-Turn Technical Assistant
[dim]Status:[/dim] {mode_text}
[dim]Context Window Strategy:[/dim] [magenta]{settings.context_strategy}[/magenta] (Limit: {settings.max_history_messages} msgs)
[dim]Commands:[/dim] [yellow]/context[/yellow] (inspect context) | [yellow]/strategy <mode>[/yellow] | [yellow]/new[/yellow] | [yellow]/help[/yellow] | [yellow]/exit[/yellow]"""

    console.print(Panel(banner_text, border_style="cyan", title="🤖 LLM Terminal Assistant", subtitle="Multi-Turn Dialog Engine"))


def show_context_inspection(session):
    total = len(session.history)
    effective_system_prompt = get_default_system_prompt()
    if session.strategy == "summarization" and session.running_summary:
        effective_system_prompt += f"\n\n### Prior Conversation Context Summary:\n{session.running_summary}"

    ctx = conversation_manager.build_llm_context(session, effective_system_prompt)

    table = Table(title="🔍 Live Context Window Inspector", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")

    table.add_row("Conversation ID", session.conversation_id[:8] + "...")
    table.add_row("Active Strategy", session.strategy)
    table.add_row("Total History Turns", str(total))
    table.add_row("Active Window Turns", str(ctx.active_context_count))
    table.add_row("Pruned Older Turns", str(ctx.pruned_count))
    table.add_row("Estimated Tokens", f"~{ctx.estimated_total_tokens}")
    table.add_row("Running Summary Active", "Yes" if ctx.has_summary else "No")

    console.print(table)

    if session.strategy == "summarization" and session.running_summary:
        console.print(Panel(session.running_summary, title="📝 Current Running Summary", border_style="magenta"))

    console.print(Panel(
        f"The LLM currently receives {ctx.active_context_count} active dialogue messages plus the persona instructions.",
        border_style="dim"
    ))


def main():
    print_banner()

    session_id = str(uuid.uuid4())
    session = conversation_manager.get_or_create_session(
        conversation_id=session_id,
        strategy=settings.context_strategy,
        max_messages=settings.max_history_messages,
        summary_trigger_threshold=settings.summary_trigger_threshold
    )

    llm = get_llm_client()

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
            if not user_input:
                continue

            # Handle Commands
            if user_input.lower() in ["/exit", "/quit", "exit", "quit"]:
                console.print("[dim]Exiting session. Goodbye![/dim]")
                break

            elif user_input.lower() == "/help":
                console.print(Panel("""
[bold]Available Commands:[/bold]
  [yellow]/context[/yellow]             - Inspect the current context window payload & token metrics
  [yellow]/strategy <mode>[/yellow]     - Switch strategy ('truncation' or 'summarization')
  [yellow]/new[/yellow]                 - Start a fresh conversation session
  [yellow]/clear[/yellow]               - Clear message history of current session
  [yellow]/exit[/yellow]                - Exit CLI
""", title="Help", border_style="blue"))
                continue

            elif user_input.lower() == "/context":
                show_context_inspection(session)
                continue

            elif user_input.lower().startswith("/strategy"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].lower() in ["truncation", "summarization"]:
                    new_strat = parts[1].lower()
                    session.strategy = new_strat
                    console.print(f"[green]✓ Strategy switched to '{new_strat}'[/green]")
                else:
                    console.print("[red]Usage: /strategy truncation OR /strategy summarization[/red]")
                continue

            elif user_input.lower() == "/new":
                session_id = str(uuid.uuid4())
                session = conversation_manager.get_or_create_session(
                    conversation_id=session_id,
                    strategy=settings.context_strategy,
                    max_messages=settings.max_history_messages
                )
                console.print(f"[green]✓ Started new conversation session: {session_id[:8]}...[/green]")
                continue

            elif user_input.lower() == "/clear":
                session.clear()
                console.print("[green]✓ Current session history cleared.[/green]")
                continue

            # Process Chat Turn
            session.add_message(role="user", content=user_input)

            # Summarization Step if applicable
            if session.strategy == "summarization":
                unsummarized = session.get_messages_for_summarization()
                if unsummarized and len(session.history) > session.summary_trigger_threshold:
                    try:
                        slice_dicts = [{"role": m.role, "content": m.content} for m in unsummarized]
                        new_summary = llm.summarize(slice_dicts, existing_summary=session.running_summary)
                        cutoff_index = len(session.history) - max(2, session.max_messages // 2)
                        session.commit_summary(new_summary, cutoff_index)
                    except Exception as sum_err:
                        console.print(f"[dim yellow]Summarization note: {sum_err}[/dim yellow]")

            # Assemble system instruction & context
            effective_system_prompt = get_default_system_prompt()
            if session.strategy == "summarization" and session.running_summary:
                effective_system_prompt += f"\n\n### Prior Conversation Context Summary:\n{session.running_summary}"

            ctx = conversation_manager.build_llm_context(session, effective_system_prompt)

            # Query LLM with spinner
            with console.status(f"[bold cyan]{settings.bot_name} is reasoning...[/bold cyan]", spinner="dots"):
                try:
                    reply = llm.generate(
                        messages=ctx.messages,
                        system_instruction=effective_system_prompt
                    )
                except LLMException as llm_err:
                    reply = f"⚠️ [System Alert: {llm_err.error_type}]\n{llm_err.message}"
                except Exception as e:
                    reply = f"⚠️ Unexpected error: {str(e)}"

            # Save assistant reply
            session.add_message(role="assistant", content=reply)

            # Display response
            meta_tag = f"[dim]Window: {ctx.active_context_count}/{ctx.total_history_count} msgs | ~{ctx.estimated_total_tokens} tokens[/dim]"
            console.print(f"\n[bold cyan]{settings.bot_name}[/bold cyan] {meta_tag}")
            console.print(Markdown(reply))

        except KeyboardInterrupt:
            console.print("\n[dim]Session interrupted. Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]CLI Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
