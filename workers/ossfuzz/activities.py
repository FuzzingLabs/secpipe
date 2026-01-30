"""
OSS-Fuzz Campaign Activities

Activities for running OSS-Fuzz campaigns using Google's infrastructure.
"""

import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import yaml
from temporalio import activity

logger = logging.getLogger(__name__)

# Paths
OSS_FUZZ_REPO = Path("/opt/oss-fuzz")
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/cache"))


@activity.defn(name="load_ossfuzz_project")
async def load_ossfuzz_project_activity(project_name: str) -> Dict[str, Any]:
    """
    Load OSS-Fuzz project configuration from project.yaml.

    Args:
        project_name: Name of the OSS-Fuzz project (e.g., "curl", "sqlite3")

    Returns:
        Dictionary with project config, paths, and metadata
    """
    logger.info(f"Loading OSS-Fuzz project: {project_name}")

    # Update OSS-Fuzz repo if it exists, clone if not
    if OSS_FUZZ_REPO.exists():
        logger.info("Updating OSS-Fuzz repository...")
        subprocess.run(
            ["git", "-C", str(OSS_FUZZ_REPO), "pull", "--depth=1"],
            check=False  # Don't fail if already up to date
        )
    else:
        logger.info("Cloning OSS-Fuzz repository...")
        subprocess.run(
            [
                "git", "clone", "--depth=1",
                "https://github.com/google/oss-fuzz.git",
                str(OSS_FUZZ_REPO)
            ],
            check=True
        )

    # Find project directory
    project_path = OSS_FUZZ_REPO / "projects" / project_name
    if not project_path.exists():
        raise ValueError(
            f"Project '{project_name}' not found in OSS-Fuzz. "
            f"Available projects: https://github.com/google/oss-fuzz/tree/master/projects"
        )

    # Read project.yaml
    config_file = project_path / "project.yaml"
    if not config_file.exists():
        raise ValueError(f"No project.yaml found for project '{project_name}'")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    # Add paths
    config["project_name"] = project_name
    config["project_path"] = str(project_path)
    config["dockerfile_path"] = str(project_path / "Dockerfile")
    config["build_script_path"] = str(project_path / "build.sh")

    # Validate required fields
    if not config.get("language"):
        logger.warning(f"No language specified in project.yaml for {project_name}")

    logger.info(
        f"✓ Loaded project {project_name}: "
        f"language={config.get('language', 'unknown')}, "
        f"engines={config.get('fuzzing_engines', [])}, "
        f"sanitizers={config.get('sanitizers', [])}"
    )

    return config


@activity.defn(name="build_ossfuzz_project")
async def build_ossfuzz_project_activity(
    project_name: str,
    project_config: Dict[str, Any],
    sanitizer: Optional[str] = None,
    engine: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build OSS-Fuzz project directly using build.sh (no Docker-in-Docker).

    Args:
        project_name: Name of the project
        project_config: Configuration from project.yaml
        sanitizer: Override sanitizer (default: first from project.yaml)
        engine: Override engine (default: first from project.yaml)

    Returns:
        Dictionary with build results and discovered fuzz targets
    """
    logger.info(f"Building OSS-Fuzz project: {project_name}")

    # Determine sanitizer and engine
    sanitizers = project_config.get("sanitizers", ["address"])
    engines = project_config.get("fuzzing_engines", ["libfuzzer"])

    use_sanitizer = sanitizer if sanitizer else sanitizers[0]
    use_engine = engine if engine else engines[0]

    logger.info(f"Building with sanitizer={use_sanitizer}, engine={use_engine}")

    # Setup directories
    src_dir = Path("/src")
    out_dir = Path("/out")
    src_dir.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)

    # Clean previous build artifacts
    for item in out_dir.glob("*"):
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)

    # Copy project files from OSS-Fuzz repo to /src
    project_path = Path(project_config["project_path"])
    build_script = project_path / "build.sh"

    if not build_script.exists():
        raise Exception(f"build.sh not found for project {project_name}")

    logger.info(f"Copying project files from {project_path} to {src_dir}")

    # Copy build.sh
    shutil.copy2(build_script, src_dir / "build.sh")
    os.chmod(src_dir / "build.sh", 0o755)

    # Copy any fuzzer source files (*.cc, *.c, *.cpp files)
    for pattern in ["*.cc", "*.c", "*.cpp", "*.h", "*.hh", "*.hpp"]:
        for src_file in project_path.glob(pattern):
            dest_file = src_dir / src_file.name
            shutil.copy2(src_file, dest_file)
            logger.info(f"Copied: {src_file.name}")

    # Clone project source code to subdirectory
    main_repo = project_config.get("main_repo")
    work_dir = src_dir

    if main_repo:
        logger.info(f"Cloning project source from {main_repo}")
        project_src_dir = src_dir / project_name

        # Remove existing directory if present
        if project_src_dir.exists():
            shutil.rmtree(project_src_dir)

        clone_cmd = ["git", "clone", "--depth=1", main_repo, str(project_src_dir)]
        result = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.warning(f"Failed to clone {main_repo}: {result.stderr}")
            logger.info("Continuing without cloning (build.sh may download source)")
        else:
            # Copy build.sh into the project source directory
            shutil.copy2(src_dir / "build.sh", project_src_dir / "build.sh")
            os.chmod(project_src_dir / "build.sh", 0o755)
            # build.sh should run from within the project directory
            work_dir = project_src_dir
            logger.info(f"Build will run from: {work_dir}")
    else:
        logger.info("No main_repo in project.yaml, build.sh will download source")

    # Set OSS-Fuzz environment variables
    build_env = os.environ.copy()
    build_env.update({
        "SRC": str(src_dir),
        "OUT": str(out_dir),
        "FUZZING_ENGINE": use_engine,
        "SANITIZER": use_sanitizer,
        "ARCHITECTURE": "x86_64",
        # Use clang's built-in libfuzzer instead of separate library
        "LIB_FUZZING_ENGINE": "-fsanitize=fuzzer",
    })

    # Set sanitizer flags
    if use_sanitizer == "address":
        build_env["CFLAGS"] = build_env.get("CFLAGS", "") + " -fsanitize=address"
        build_env["CXXFLAGS"] = build_env.get("CXXFLAGS", "") + " -fsanitize=address"
    elif use_sanitizer == "memory":
        build_env["CFLAGS"] = build_env.get("CFLAGS", "") + " -fsanitize=memory"
        build_env["CXXFLAGS"] = build_env.get("CXXFLAGS", "") + " -fsanitize=memory"
    elif use_sanitizer == "undefined":
        build_env["CFLAGS"] = build_env.get("CFLAGS", "") + " -fsanitize=undefined"
        build_env["CXXFLAGS"] = build_env.get("CXXFLAGS", "") + " -fsanitize=undefined"

    # Execute build.sh from the work directory
    logger.info(f"Executing build.sh in {work_dir}")
    build_cmd = ["bash", "./build.sh"]

    result = subprocess.run(
        build_cmd,
        cwd=str(work_dir),
        env=build_env,
        capture_output=True,
        text=True,
        timeout=1800  # 30 minutes max build time
    )

    if result.returncode != 0:
        logger.error(f"Build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        raise Exception(f"Build failed for {project_name}: {result.stderr}")

    logger.info("✓ Build completed successfully")
    logger.info(f"Build output:\n{result.stdout[-2000:]}")  # Last 2000 chars

    # Discover fuzz targets in /out
    fuzz_targets = []
    for file in out_dir.glob("*"):
        if file.is_file() and os.access(file, os.X_OK):
            # Check if it's a fuzz target (executable, not .so/.a/.o)
            if file.suffix not in ['.so', '.a', '.o', '.zip']:
                fuzz_targets.append(str(file))
                logger.info(f"Found fuzz target: {file.name}")

    if not fuzz_targets:
        logger.warning(f"No fuzz targets found in {out_dir}")
        logger.info(f"Directory contents: {list(out_dir.glob('*'))}")

    return {
        "fuzz_targets": fuzz_targets,
        "build_log": result.stdout[-5000:],  # Last 5000 chars
        "sanitizer_used": use_sanitizer,
        "engine_used": use_engine,
        "out_dir": str(out_dir)
    }


@activity.defn(name="fuzz_target")
async def fuzz_target_activity(
    target_path: str,
    engine: str,
    duration_seconds: int,
    corpus_dir: Optional[str] = None,
    dict_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run fuzzing on a target with specified engine.

    Args:
        target_path: Path to fuzz target executable
        engine: Fuzzing engine (libfuzzer, afl, honggfuzz)
        duration_seconds: How long to fuzz
        corpus_dir: Optional corpus directory
        dict_file: Optional dictionary file

    Returns:
        Dictionary with fuzzing stats and results
    """
    logger.info(f"Fuzzing {Path(target_path).name} with {engine} for {duration_seconds}s")

    # Prepare corpus directory
    if not corpus_dir:
        corpus_dir = str(CACHE_DIR / "corpus" / Path(target_path).stem)
        Path(corpus_dir).mkdir(parents=True, exist_ok=True)

    output_dir = CACHE_DIR / "output" / Path(target_path).stem
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now()

    try:
        if engine == "libfuzzer":
            cmd = [
                target_path,
                corpus_dir,
                f"-max_total_time={duration_seconds}",
                "-print_final_stats=1",
                f"-artifact_prefix={output_dir}/"
            ]
            if dict_file:
                cmd.append(f"-dict={dict_file}")

        elif engine == "afl":
            cmd = [
                "afl-fuzz",
                "-i", corpus_dir if Path(corpus_dir).glob("*") else "-",  # Empty corpus OK
                "-o", str(output_dir),
                "-t", "1000",  # Timeout per execution
                "-m", "none",  # No memory limit
                "--", target_path, "@@"
            ]

        elif engine == "honggfuzz":
            cmd = [
                "honggfuzz",
                f"--run_time={duration_seconds}",
                "-i", corpus_dir,
                "-o", str(output_dir),
                "--", target_path
            ]

        else:
            raise ValueError(f"Unsupported fuzzing engine: {engine}")

        logger.info(f"Starting fuzzer: {' '.join(cmd[:5])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration_seconds + 120  # Add 2 minute buffer
        )

        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()

        # Parse stats from output
        stats = parse_fuzzing_stats(result.stdout, result.stderr, engine)
        stats["elapsed_time"] = elapsed
        stats["target_name"] = Path(target_path).name
        stats["engine"] = engine

        # Find crashes
        crashes = find_crashes(output_dir)
        stats["crashes"] = len(crashes)
        stats["crash_files"] = crashes

        # Collect new corpus files
        new_corpus = collect_corpus(corpus_dir)
        stats["corpus_size"] = len(new_corpus)
        stats["corpus_files"] = new_corpus

        logger.info(
            f"✓ Fuzzing completed: {stats.get('total_executions', 0)} execs, "
            f"{len(crashes)} crashes"
        )

        return stats

    except subprocess.TimeoutExpired:
        logger.warning(f"Fuzzing timed out after {duration_seconds}s")
        return {
            "target_name": Path(target_path).name,
            "engine": engine,
            "status": "timeout",
            "elapsed_time": duration_seconds
        }


def parse_fuzzing_stats(stdout: str, stderr: str, engine: str) -> Dict[str, Any]:
    """Parse fuzzing statistics from output"""
    stats = {}

    if engine == "libfuzzer":
        # Parse libFuzzer stats
        for line in (stdout + stderr).split('\n'):
            if "#" in line and "NEW" in line:
                # Example: #8192 NEW    cov: 1234 ft: 5678 corp: 89/10KB
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith("cov:"):
                        stats["coverage"] = int(parts[i+1])
                    elif part.startswith("corp:"):
                        stats["corpus_entries"] = int(parts[i+1].split('/')[0])
                    elif part.startswith("exec/s:"):
                        stats["executions_per_sec"] = float(parts[i+1])
                    elif part.startswith("#"):
                        stats["total_executions"] = int(part[1:])

    elif engine == "afl":
        # Parse AFL stats (would need to read fuzzer_stats file)
        pass

    elif engine == "honggfuzz":
        # Parse Honggfuzz stats
        pass

    return stats


def find_crashes(output_dir: Path) -> List[str]:
    """Find crash files in output directory"""
    crashes = []

    # libFuzzer crash files start with "crash-" or "leak-"
    for pattern in ["crash-*", "leak-*", "timeout-*"]:
        crashes.extend([str(f) for f in output_dir.glob(pattern)])

    # AFL crashes in crashes/ subdirectory
    crashes_dir = output_dir / "crashes"
    if crashes_dir.exists():
        crashes.extend([str(f) for f in crashes_dir.glob("*") if f.is_file()])

    return crashes


def collect_corpus(corpus_dir: str) -> List[str]:
    """Collect corpus files"""
    corpus_path = Path(corpus_dir)
    if not corpus_path.exists():
        return []

    return [str(f) for f in corpus_path.glob("*") if f.is_file()]
