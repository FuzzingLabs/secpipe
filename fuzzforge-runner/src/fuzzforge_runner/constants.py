"""FuzzForge Runner constants."""

from pydantic import UUID7

#: Type alias for execution identifiers.
type FuzzForgeExecutionIdentifier = UUID7

#: Default directory name for module input inside sandbox.
SANDBOX_INPUT_DIRECTORY: str = "/fuzzforge/input"

#: Default directory name for module output inside sandbox.
SANDBOX_OUTPUT_DIRECTORY: str = "/fuzzforge/output"

#: Default archive filename for results.
RESULTS_ARCHIVE_FILENAME: str = "results.tar.gz"

#: Default configuration filename.
MODULE_CONFIG_FILENAME: str = "config.json"

#: Module entrypoint script name.
MODULE_ENTRYPOINT: str = "module"
