import os
import sys
import yaml
from rich.console import Console
from core.agent import ExcelAgent


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        print(f"Error: configuration file '{path}' not found.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    console = Console()
    console.print("[bold cyan]Excel Automation Agent[/bold cyan]")
    
    config = load_config()
    
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        # Check if there are any files in input/ directory
        input_dir = config.get("paths", {}).get("input_dir", "input")
        os.makedirs(input_dir, exist_ok=True)
        files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        
        if files:
            source = files[0]
            console.print(f"[green]Using file from input directory: {source}[/green]")
        else:
            console.print("No input provided. Please provide text or an input file.")
            source = input("Enter text or file path to convert to Excel: ")

    if not source.strip():
        console.print("[red]Input cannot be empty. Exiting.[/red]")
        sys.exit(1)
        
    agent = ExcelAgent(config)
    
    console.print("\n[bold yellow]Starting Autonomous Loop...[/bold yellow]")
    try:
        success = agent.run(source)
        if success:
            console.print(f"\n[bold green]Success![/bold green] Output saved to: {agent.state.output_path}")
        else:
            console.print("\n[bold red]Execution failed after retries and reflections.[/bold red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Execution aborted by user.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
