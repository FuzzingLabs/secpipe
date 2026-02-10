"""FuzzForge Runner constants."""

#: Default directory name for module input inside sandbox.
SANDBOX_INPUT_DIRECTORY: str = "/data/input"

#: Default directory name for module output inside sandbox.
SANDBOX_OUTPUT_DIRECTORY: str = "/data/output"

#: Default archive filename for results.
RESULTS_ARCHIVE_FILENAME: str = "results.tar.gz"

#: Default configuration filename.
MODULE_CONFIG_FILENAME: str = "config.json"

#: Module entrypoint script name.
MODULE_ENTRYPOINT: str = "module"
