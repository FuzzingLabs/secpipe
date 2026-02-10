"""Helper utilities for working with bridge transformations."""

from pathlib import Path
from typing import Any


def load_transform_from_file(file_path: str | Path) -> str:
    """Load bridge transformation code from a Python file.
    
    This reads the transformation function from a .py file and extracts
    the code as a string suitable for the bridge module.
    
    Args:
        file_path: Path to Python file containing transform() function
        
    Returns:
        Python code as a string
        
    Example:
        >>> code = load_transform_from_file("transformations/add_line_numbers.py")
        >>> # code contains the transform() function as a string

    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Transformation file not found: {file_path}")

    if path.suffix != ".py":
        raise ValueError(f"Transformation file must be .py file, got: {path.suffix}")

    # Read the entire file
    code = path.read_text()

    return code


def create_bridge_input(
    transform_file: str | Path,
    input_filename: str | None = None,
    output_filename: str | None = None,
) -> dict[str, Any]:
    """Create bridge module input configuration from a transformation file.
    
    Args:
        transform_file: Path to Python file with transform() function
        input_filename: Optional specific input file to transform
        output_filename: Optional specific output filename
        
    Returns:
        Dictionary suitable for bridge module's input.json
        
    Example:
        >>> config = create_bridge_input("transformations/add_line_numbers.py")
        >>> import json
        >>> json.dump(config, open("input.json", "w"))

    """
    code = load_transform_from_file(transform_file)

    return {
        "code": code,
        "input_filename": input_filename,
        "output_filename": output_filename,
    }


def validate_transform_function(file_path: str | Path) -> bool:
    """Validate that a Python file contains a valid transform() function.
    
    Args:
        file_path: Path to Python file to validate
        
    Returns:
        True if valid, raises exception otherwise
        
    Raises:
        ValueError: If transform() function is not found or invalid

    """
    code = load_transform_from_file(file_path)

    # Check if transform function is defined
    if "def transform(" not in code:
        raise ValueError(
            f"File {file_path} must contain a 'def transform(data)' function"
        )

    # Try to compile the code
    try:
        compile(code, str(file_path), "exec")
    except SyntaxError as e:
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    # Try to execute and verify transform exists
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    try:
        exec(code, namespace)
    except Exception as e:
        raise ValueError(f"Failed to execute {file_path}: {e}") from e

    if "transform" not in namespace:
        raise ValueError(f"No 'transform' function found in {file_path}")

    if not callable(namespace["transform"]):
        raise ValueError(f"'transform' in {file_path} is not callable")

    return True
