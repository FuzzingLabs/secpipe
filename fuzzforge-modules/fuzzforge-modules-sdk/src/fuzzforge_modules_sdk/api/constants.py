from pathlib import Path

PATH_TO_DATA: Path = Path("/data")
PATH_TO_INPUTS: Path = PATH_TO_DATA.joinpath("input")
PATH_TO_INPUT: Path = PATH_TO_INPUTS.joinpath("input.json")
PATH_TO_OUTPUTS: Path = PATH_TO_DATA.joinpath("output")
PATH_TO_ARTIFACTS: Path = PATH_TO_OUTPUTS.joinpath("artifacts")
PATH_TO_RESULTS: Path = PATH_TO_OUTPUTS.joinpath("results.json")
PATH_TO_LOGS: Path = PATH_TO_OUTPUTS.joinpath("logs.jsonl")

# Streaming output paths for real-time progress
PATH_TO_PROGRESS: Path = PATH_TO_OUTPUTS.joinpath("progress.json")
PATH_TO_STREAM: Path = PATH_TO_OUTPUTS.joinpath("stream.jsonl")
