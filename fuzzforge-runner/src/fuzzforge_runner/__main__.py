"""FuzzForge Runner CLI entry point."""

from fuzzforge_runner.runner import Runner
from fuzzforge_runner.settings import Settings


def main() -> None:
    """Entry point for the FuzzForge Runner CLI.

    This is a minimal entry point that can be used for testing
    and direct execution. The primary interface is via the MCP server.

    """
    import argparse

    parser = argparse.ArgumentParser(description="FuzzForge Runner")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args()

    if args.version:
        print("fuzzforge-runner 0.0.1")  # noqa: T201
        return

    print("FuzzForge Runner - Use via MCP server or programmatically")  # noqa: T201


if __name__ == "__main__":
    main()
