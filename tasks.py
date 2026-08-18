"""Invoke tasks for the Docker development environment."""

from typing import TYPE_CHECKING

from invoke.context import Context

if TYPE_CHECKING:
    from collections.abc import Callable

    # Typed stand-in for invoke's partially typed task decorator
    def task(_func: Callable[..., None]) -> Callable[..., None]: ...

else:
    from invoke.tasks import task

_RUN = "docker compose run --rm dev"


@task
def build(context: Context) -> None:
    """Build the Docker development image."""
    context.run("docker compose build", pty=True)


@task
def docs(context: Context) -> None:
    """Serve the documentation with live reload at http://localhost:8001."""
    context.run("docker compose --profile docs up docs", pty=True)


@task
def pytest(context: Context, *, coverage: bool = False) -> None:
    """Run the test suite inside the development container."""
    command = "python scripts/build.py pytest --coverage" if coverage else "pytest"
    context.run(f"{_RUN} {command}", pty=True)


@task
def lint(context: Context, *, fix: bool = False) -> None:
    """Run all linters and type checkers inside the development container."""
    context.run(
        f"{_RUN} python scripts/build.py lint{' --fix' if fix else ''}",
        pty=True,
    )


@task
def lint_and_test(context: Context) -> None:
    """Run the full lint + test suite (what CI runs) inside the development container."""
    context.run(f"{_RUN} python scripts/build.py lint-and-test", pty=True)


@task
def cli(context: Context) -> None:
    """Open a shell inside the development container."""
    context.run(f"{_RUN} bash", pty=True)


@task
def sync_standards(context: Context, *, apply: bool = False) -> None:
    """Check drift against the published canonical standards (--apply to update)."""
    action = "apply" if apply else "check"
    context.run(f"{_RUN} python scripts/sync_standards.py {action}", pty=True)


@task
def destroy(context: Context) -> None:
    """Stop and remove the development containers."""
    context.run("docker compose --profile docs down --remove-orphans", pty=True)
