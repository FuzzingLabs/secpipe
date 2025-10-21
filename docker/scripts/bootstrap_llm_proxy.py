"""Bootstrap the Bifrost proxy with providers and default virtual keys.

This script runs inside a one-shot container during docker-compose startup.
It will:
  1. Wait for the proxy health endpoint to respond.
  2. Configure any upstream providers for which an env key is present.
  3. Create (or reuse) the default virtual key for the task agent.
  4. Persist the generated key back into volumes/env/.env so the agent uses it.

The script is idempotent: rerunning it leaves existing configs in place and skips
key generation if OPENAI_API_KEY already contains a proxy-issued key.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

PROXY_BASE_URL = os.getenv("PROXY_BASE_URL", "http://llm-proxy:8080").rstrip("/")
ENV_FILE_PATH = Path(os.getenv("ENV_FILE_PATH", "/bootstrap/env/.env"))
BIFROST_ENV_FILE_PATH = Path(
    os.getenv("BIFROST_ENV_FILE_PATH", "/bootstrap/env/.env.bifrost")
)
CONFIG_FILE_PATH = Path(os.getenv("CONFIG_FILE_PATH", "/bootstrap/data/config.json"))
DEFAULT_VIRTUAL_KEY_NAME = "task-agent default"
DEFAULT_VIRTUAL_KEY_USER = "fuzzforge-task-agent"
PLACEHOLDER_KEY = "sk-proxy-default"
MAX_WAIT_SECONDS = 120

DEFAULT_PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-5"],
}


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    env_var: str
    fallback_env_vars: tuple[str, ...] = ()

    @property
    def env_reference(self) -> str:
        return f"env.{self.env_var}"


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("openai", "BIFROST_OPENAI_KEY", ("OPENAI_API_KEY",)),
    ProviderSpec("anthropic", "BIFROST_ANTHROPIC_KEY", ("ANTHROPIC_API_KEY",)),
    ProviderSpec("gemini", "BIFROST_GEMINI_KEY", ("GEMINI_API_KEY",)),
    ProviderSpec("mistral", "BIFROST_MISTRAL_KEY", ("MISTRAL_API_KEY",)),
    ProviderSpec("openrouter", "BIFROST_OPENROUTER_KEY", ("OPENROUTER_API_KEY",)),
)


UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def looks_like_virtual_key(candidate: str | None) -> bool:
    if not candidate:
        return False
    value = candidate.strip()
    if not value or value == PLACEHOLDER_KEY:
        return False
    if UUID_PATTERN.match(value):
        return True
    if value.startswith("sk-proxy-"):
        return True
    return False


def set_env_value(lines: list[str], key: str, value: str) -> tuple[list[str], bool]:
    prefix = f"{key}="
    new_line = f"{prefix}{value}"
    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(prefix):
            if lines[idx].lstrip() == new_line:
                return lines, False
            indent = line[: len(line) - len(stripped)]
            lines[idx] = f"{indent}{new_line}"
            return lines, True
    lines.append(new_line)
    return lines, True


def parse_env_lines(lines: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        mapping[key] = value
    return mapping


def resolve_provider_key(
    provider: ProviderSpec,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> tuple[str | None, str | None, str | None]:
    candidate = bifrost_map.get(provider.env_var)
    if candidate:
        value = candidate.strip()
        if value:
            return value, provider.env_var, "bifrost"

    candidate = env_map.get(provider.env_var)
    if candidate:
        value = candidate.strip()
        if value and value != PLACEHOLDER_KEY:
            return value, provider.env_var, "env"

    candidate = os.getenv(provider.env_var)
    if candidate:
        value = candidate.strip()
        if value and value != PLACEHOLDER_KEY:
            return value, provider.env_var, "env"

    for var in provider.fallback_env_vars:
        raw_value = env_map.get(var) or os.getenv(var)
        if not raw_value:
            continue
        value = raw_value.strip()
        if not value or value == PLACEHOLDER_KEY:
            continue
        if var == "OPENAI_API_KEY" and looks_like_virtual_key(value):
            continue
        return value, var, "fallback"

    return None, None, None


def ensure_provider_env_export(
    lines: list[str], provider: ProviderSpec, key_value: str
) -> tuple[list[str], bool]:
    # Store provider secrets under their dedicated BIFROST_* variables so future
    # restarts inject them into the proxy container environment automatically.
    updated_lines, changed = set_env_value(lines, provider.env_var, key_value)
    if changed:
        os.environ[provider.env_var] = key_value
    return updated_lines, changed


def get_models_for_provider(
    provider: ProviderSpec,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> list[str]:
    env_var = f"BIFROST_{provider.name.upper()}_MODELS"
    raw_value = (
        os.getenv(env_var)
        or env_map.get(env_var)
        or bifrost_map.get(env_var)
    )
    if raw_value:
        models = [item.strip() for item in raw_value.split(",") if item.strip()]
        if models:
            return models
    return DEFAULT_PROVIDER_MODELS.get(provider.name, [])


def _should_use_responses_api(
    provider: ProviderSpec,
    models: list[str],
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> bool:
    if provider.name != "openai":
        return False

    env_var = "BIFROST_OPENAI_USE_RESPONSES_API"
    raw_value = (
        os.getenv(env_var)
        or env_map.get(env_var)
        or bifrost_map.get(env_var)
    )
    if raw_value and raw_value.strip().lower() in {"1", "true", "yes", "on"}:
        return True

    for model in models:
        suffix = model.split("/", 1)[-1]
        if suffix.startswith("gpt-5") or suffix.startswith("o1"):
            return True
    return False


def _read_positive_int(
    candidate: str | None,
    *,
    var_name: str,
) -> int | None:
    if candidate is None:
        return None
    value = candidate.strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        log(f"Ignoring non-integer timeout for {var_name}: {value}")
        return None
    if parsed <= 0:
        log(f"Ignoring non-positive timeout for {var_name}: {parsed}")
        return None
    return parsed


def _lookup_timeout_var(
    var_name: str,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> int | None:
    for source in (
        bifrost_map.get(var_name),
        env_map.get(var_name),
        os.getenv(var_name),
    ):
        parsed = _read_positive_int(source, var_name=var_name)
        if parsed is not None:
            return parsed
    return None


def _get_timeout_seconds(
    provider: ProviderSpec,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> int | None:
    provider_specific_var = f"BIFROST_{provider.name.upper()}_TIMEOUT_SECONDS"
    timeout = _lookup_timeout_var(provider_specific_var, env_map, bifrost_map)
    if timeout is not None:
        return timeout
    return _lookup_timeout_var("BIFROST_DEFAULT_TIMEOUT_SECONDS", env_map, bifrost_map)


def build_network_config(
    provider: ProviderSpec,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
) -> dict[str, object] | None:
    timeout = _get_timeout_seconds(provider, env_map, bifrost_map)
    if timeout is None:
        return None
    return {"default_request_timeout_in_seconds": timeout}


def build_provider_config_entry(
    provider: ProviderSpec,
    env_map: dict[str, str],
    bifrost_map: dict[str, str],
    *,
    network_config: dict[str, object] | None = None,
) -> dict[str, object]:
    models = get_models_for_provider(provider, env_map, bifrost_map)
    key_entry: dict[str, object] = {
        "value": provider.env_reference,
        "models": models,
        "weight": 1.0,
    }
    if _should_use_responses_api(provider, models, env_map, bifrost_map):
        key_entry["openai_key_config"] = {"use_responses_api": True}

    entry: dict[str, object] = {"keys": [key_entry]}
    if network_config:
        entry["network_config"] = network_config
    return entry


def _default_client_config() -> dict[str, object]:
    return {"drop_excess_requests": False}


def _default_config_store_config() -> dict[str, object]:
    return {
        "enabled": True,
        "type": "sqlite",
        "config": {"path": "./config.db"},
    }


def update_config_file(
    providers_config: dict[str, dict[str, object]],
    virtual_key_value: str | None = None,
) -> None:
    if not providers_config:
        return

    config_data: dict[str, object]
    if CONFIG_FILE_PATH.exists():
        try:
            config_data = json.loads(CONFIG_FILE_PATH.read_text() or "{}")
        except json.JSONDecodeError:
            log(
                "Existing config.json is invalid JSON; regenerating from provider metadata"
            )
            config_data = {}
    else:
        config_data = {}

    providers_section = config_data.setdefault("providers", {})
    config_data.setdefault("client", _default_client_config())
    config_data.setdefault("config_store", _default_config_store_config())

    changed = False
    for name, entry in providers_config.items():
        if providers_section.get(name) != entry:
            providers_section[name] = entry
            changed = True

    if virtual_key_value:
        governance_section = config_data.setdefault("governance", {})
        vk_list: list[dict[str, object]] = governance_section.setdefault(
            "virtual_keys", []
        )

        provider_configs = []
        for provider_name, entry in providers_config.items():
            allowed_models: list[str] = []
            for key_entry in entry.get("keys", []):
                models = key_entry.get("models", [])
                if models:
                    allowed_models.extend(models)
            provider_configs.append(
                {
                    "provider": provider_name,
                    "weight": 1.0,
                    "allowed_models": allowed_models,
                }
            )

        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        virtual_key_entry = {
            "id": f"{DEFAULT_VIRTUAL_KEY_USER}-vk",
            "name": DEFAULT_VIRTUAL_KEY_NAME,
            "description": "Default virtual key issued during bootstrap",
            "value": virtual_key_value,
            "is_active": True,
            "provider_configs": provider_configs,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        matched = False
        for existing in vk_list:
            if existing.get("name") == DEFAULT_VIRTUAL_KEY_NAME or existing.get(
                "id"
            ) == virtual_key_entry["id"]:
                existing.update(virtual_key_entry)
                matched = True
                changed = True
                break

        if not matched:
            vk_list.append(virtual_key_entry)
            changed = True

    if not changed:
        return

    CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE_PATH.write_text(json.dumps(config_data, indent=2, sort_keys=True) + "\n")
    log(f"Wrote provider config to {CONFIG_FILE_PATH}")


def log(message: str) -> None:
    print(f"[llm-proxy-bootstrap] {message}", flush=True)


def wait_for_proxy() -> None:
    url = f"{PROXY_BASE_URL}/health"
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url) as response:  # noqa: S310
                if response.status == 200:
                    log("Proxy health endpoint is reachable")
                    return
        except urllib.error.URLError as exc:  # pragma: no cover - best effort logging
            log(f"Proxy not ready yet: {exc}")
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for {url}")


def request_json(path: str, *, method: str = "GET", payload: dict | None = None) -> tuple[int, str]:
    url = f"{PROXY_BASE_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body


def post_json(path: str, payload: dict) -> tuple[int, str]:
    return request_json(path, method="POST", payload=payload)


def get_json(path: str) -> tuple[int, str]:
    return request_json(path, method="GET")


def configure_providers() -> dict[str, dict[str, object]]:
    env_map = parse_env_lines(read_env_file())
    bifrost_lines = read_bifrost_env_file()
    bifrost_map = parse_env_lines(bifrost_lines)
    bifrost_lines_changed = False
    config_updates: dict[str, dict[str, object]] = {}

    for provider in PROVIDERS:
        key_value, _source_var, _ = resolve_provider_key(provider, env_map, bifrost_map)
        if not key_value:
            continue

        network_config = build_network_config(provider, env_map, bifrost_map)
        payload = {
            "provider": provider.name,
            "keys": [
                {
                    "value": key_value,
                    "models": [],
                    "weight": 1.0,
                }
            ],
        }
        if network_config:
            payload["network_config"] = network_config
        status, body = post_json("/api/providers", payload)
        if status in {200, 201}:
            log(f"Configured provider '{provider.name}'")
        elif status == 409:
            log(f"Provider '{provider.name}' already exists (409)")
        else:
            log(
                "Failed to configure provider '%s' (%s): %s"
                % (provider.name, status, body)
            )
            continue

        os.environ[provider.env_var] = key_value
        if bifrost_map.get(provider.env_var, "") != key_value:
            bifrost_lines, changed = ensure_provider_env_export(
                bifrost_lines, provider, key_value
            )
            if changed:
                bifrost_lines_changed = True
                bifrost_map[provider.env_var] = key_value

        config_updates[provider.name] = build_provider_config_entry(
            provider,
            env_map,
            bifrost_map,
            network_config=network_config,
        )

    if bifrost_lines_changed:
        write_bifrost_env_file(bifrost_lines)
    return config_updates


def read_env_file() -> list[str]:
    if not ENV_FILE_PATH.exists():
        raise FileNotFoundError(
            f"Expected env file at {ENV_FILE_PATH}. Copy volumes/env/.env.example first."
        )
    return ENV_FILE_PATH.read_text().splitlines()


def write_env_file(lines: Iterable[str]) -> None:
    ENV_FILE_PATH.write_text("\n".join(lines) + "\n")


def read_bifrost_env_file() -> list[str]:
    if not BIFROST_ENV_FILE_PATH.exists():
        return []
    return BIFROST_ENV_FILE_PATH.read_text().splitlines()


def write_bifrost_env_file(lines: Iterable[str]) -> None:
    BIFROST_ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BIFROST_ENV_FILE_PATH.write_text("\n".join(lines) + "\n")


def current_env_key() -> str | None:
    existing = os.getenv("OPENAI_API_KEY")
    if existing:
        return existing.strip()
    # Fall back to reading file if not present in the container environment
    for line in read_env_file():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip()
    return None


def _extract_key_value(record: Mapping[str, object]) -> str | None:
    value = record.get("value") or record.get("key")
    if value:
        return str(value)
    budget = record.get("virtual_key") if isinstance(record.get("virtual_key"), Mapping) else None
    if isinstance(budget, Mapping):
        inner_value = budget.get("value") or budget.get("key")
        if inner_value:
            return str(inner_value)
    return None


def find_existing_virtual_key() -> Mapping[str, object] | None:
    status, body = get_json("/api/governance/virtual-keys")
    if status != 200:
        log(f"Could not list virtual keys ({status}): {body}")
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        log(f"Failed to parse virtual key list: {exc}")
        return None

    candidates: Sequence[Mapping[str, object]]
    if isinstance(data, dict) and "virtual_keys" in data and isinstance(data["virtual_keys"], list):
        candidates = [item for item in data["virtual_keys"] if isinstance(item, Mapping)]
    elif isinstance(data, list):
        candidates = [item for item in data if isinstance(item, Mapping)]
    else:
        log("Virtual key list response in unexpected format; skipping lookup")
        return None

    for item in candidates:
        if str(item.get("name", "")).strip() == DEFAULT_VIRTUAL_KEY_NAME:
            return item
    return None


def upsert_virtual_key() -> str | None:
    existing_env = current_env_key()

    record = find_existing_virtual_key()
    if record:
        key = _extract_key_value(record)
        if key:
            log("Reusing existing virtual key from proxy store")
            return key

    if existing_env and looks_like_virtual_key(existing_env):
        log(
            "Virtual key present in env but not found in proxy store; issuing a new key"
        )

    payload = {
        "name": DEFAULT_VIRTUAL_KEY_NAME,
        "user_id": DEFAULT_VIRTUAL_KEY_USER,
        "budget": {"max_limit": 25.0, "reset_duration": "7d"},
    }
    status, body = post_json("/api/governance/virtual-keys", payload)
    if status not in {200, 201}:
        log(f"Failed to create virtual key ({status}): {body}")
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        log(f"Could not parse virtual key response: {exc}")
        return None
    key = _extract_key_value(data)
    if not key:
        log(f"Virtual key response missing key field: {body}")
        return None
    log("Generated new virtual key for task agent")
    return key


def persist_key_to_env_file(new_key: str) -> None:
    lines = read_env_file()
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith("OPENAI_API_KEY="):
            lines[idx] = f"OPENAI_API_KEY={new_key}"
            updated = True
            break
    if not updated:
        lines.append(f"OPENAI_API_KEY={new_key}")
    write_env_file(lines)
    log(f"Wrote virtual key to {ENV_FILE_PATH}")
    os.environ["OPENAI_API_KEY"] = new_key


def main() -> int:
    log("Bootstrapping Bifrost proxy")
    try:
        wait_for_proxy()
        providers_config = configure_providers()
        existing_key = current_env_key()
        new_key = upsert_virtual_key()
        virtual_key_value = new_key or existing_key
        if new_key and new_key != existing_key:
            persist_key_to_env_file(new_key)
        update_config_file(providers_config, virtual_key_value)
        log("Bootstrap complete")
        return 0
    except Exception as exc:  # pragma: no cover - startup failure reported to logs
        log(f"Bootstrap failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
