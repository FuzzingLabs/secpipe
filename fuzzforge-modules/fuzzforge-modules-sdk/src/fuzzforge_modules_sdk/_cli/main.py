from argparse import ArgumentParser
from pathlib import Path

from fuzzforge_modules_sdk._cli.build_base_image import build_base_image
from fuzzforge_modules_sdk._cli.create_new_module import create_new_module


def create_parser() -> ArgumentParser:
    parser: ArgumentParser = ArgumentParser(
        prog="fuzzforge-modules-sdk", description="Utilities for the Fuzzforge Modules SDK."
    )

    subparsers = parser.add_subparsers(required=True)

    # fuzzforge-modules-sdk build ...
    parser_build = subparsers.add_parser(name="build")

    subparsers_build = parser_build.add_subparsers(required=True)

    # fuzzforge-modules-sdk build image ...
    parser_build_image = subparsers_build.add_parser(
        name="image",
        help="Build the image.",
    )
    parser_build_image.add_argument(
        "--engine",
        default="podman",
    )
    parser_build_image.add_argument(
        "--socket",
        default=None,
    )
    parser_build_image.set_defaults(
        function_to_execute=build_base_image,
    )

    # fuzzforge-modules-sdk new ...
    parser_new = subparsers.add_parser(name="new")

    subparsers_new = parser_new.add_subparsers(required=True)

    # fuzzforge-modules-sdk new module ...
    parser_new_module = subparsers_new.add_parser(
        name="module",
        help="Generate the boilerplate required to create a new module.",
    )
    parser_new_module.add_argument(
        "--name",
        help="The name of the module to create.",
        required=True,
    )
    parser_new_module.add_argument(
        "--directory",
        default=".",
        type=Path,
        help="The directory the new module should be created into (defaults to current working directory).",
    )
    parser_new_module.set_defaults(
        function_to_execute=create_new_module,
    )

    return parser


def main() -> None:
    """Entry point for the command-line interface."""
    parser: ArgumentParser = create_parser()
    arguments = parser.parse_args()
    function_to_execute = arguments.function_to_execute
    del arguments.function_to_execute
    function_to_execute(**vars(arguments))
