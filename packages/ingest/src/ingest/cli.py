import typer

from ingest import __version__

app = typer.Typer(help="Mizaj Google Health ingest CLI", no_args_is_help=True)


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
