#!/usr/bin/env python3
"""
JSON Config Manager — Read, update, and validate JSON configuration files.

Features:
  - Load/save JSON configs with automatic backup
    - Dot-notation access for nested keys (e.g., "database.host")
      - Schema validation with type checking
        - Environment variable interpolation (e.g., "${ENV_VAR}")
          - Merge multiple config files with priority ordering

          Usage:
            python json_config_manager.py config.json --get database.host
              python json_config_manager.py config.json --set database.port 5432
                python json_config_manager.py config.json --validate schema.json
                  python json_config_manager.py base.json overlay.json --merge output.json
                  """

import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class ConfigManager:
      """Manages JSON configuration files with dot-notation access and validation."""

    def __init__(self, filepath: Optional[str] = None, auto_backup: bool = True):
              self.filepath = Path(filepath) if filepath else None
              self.auto_backup = auto_backup
              self._data: Dict[str, Any] = {}
              if filepath and Path(filepath).exists():
                            self.load(filepath)

          def load(self, filepath: str) -> "ConfigManager":
                    """Load a JSON config file."""
                    path = Path(filepath)
                    if not path.exists():
                                  raise FileNotFoundError(f"Config file not found: {filepath}")
                              with open(path, "r", encoding="utf-8") as f:
                                            self._data = json.load(f)
                                        self.filepath = path
        return self

    def save(self, filepath: Optional[str] = None, indent: int = 2) -> Path:
              """Save config to file, creating a backup of the original if it exists."""
        target = Path(filepath) if filepath else self.filepath
        if not target:
                      raise ValueError("No filepath specified for saving config")
                  if self.auto_backup and target.exists():
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                backup_path = target.with_suffix(f".backup_{timestamp}.json")
                                shutil.copy2(target, backup_path)
                            target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
                      json.dump(self._data, f, indent=indent, ensure_ascii=False)
                  return target

    def get(self, key: str, default: Any = None) -> Any:
              """Get a value using dot-notation (e.g., 'database.host')."""
        keys = key.split(".")
        current = self._data
        for k in keys:
                      if isinstance(current, dict) and k in current:
                                        current = current[k]
else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
              """Set a value using dot-notation, creating intermediate dicts as needed."""
        keys = key.split(".")
        current = self._data
        for k in keys[:-1]:
                      if k not in current or not isinstance(current[k], dict):
                                        current[k] = {}
                                    current = current[k]
        current[keys[-1]] = value

    def delete(self, key: str) -> bool:
              """Delete a key using dot-notation. Returns True if the key existed."""
        keys = key.split(".")
        current = self._data
        for k in keys[:-1]:
                      if isinstance(current, dict) and k in current:
                                        current = current[k]
else:
                return False
        if isinstance(current, dict) and keys[-1] in current:
                      del current[keys[-1]]
            return True
        return False

    def interpolate_env(self, data: Optional[Dict] = None) -> Dict[str, Any]:
              """Replace ${ENV_VAR} patterns with actual environment variable values."""
        if data is None:
                      data = self._data
        env_pattern = re.compile(r"\$\{([^}]+)\}")

        def _resolve(obj: Any) -> Any:
                      if isinstance(obj, str):
                                        def _replacer(match):
                                                              var_name = match.group(1)
                                                              env_val = os.environ.get(var_name)
                                                              if env_val is None:
                                                                                        raise KeyError(f"Environment variable not set: {var_name}")
                                                                                    return env_val
                                                          return env_pattern.sub(_replacer, obj)
elif isinstance(obj, dict):
                return {k: _resolve(v) for k, v in obj.items()}
elif isinstance(obj, list):
                return [_resolve(item) for item in obj]
            return obj

        self._data = _resolve(data)
        return self._data

    def validate(self, schema: Dict[str, Any]) -> List[str]:
              """Validate config against a simple type schema. Returns list of errors."""
        errors = []
        self._validate_recursive(self._data, schema, "", errors)
        return errors

    def _validate_recursive(
              self, data: Any, schema: Any, path: str, errors: List[str]
    ) -> None:
              """Recursively validate data against schema definition."""
        if isinstance(schema, dict) and "type" in schema:
                      expected = schema["type"]
            type_map = {
                              "string": str, "number": (int, float), "integer": int,
                              "boolean": bool, "array": list, "object": dict,
            }
            if expected in type_map and not isinstance(data, type_map[expected]):
                              errors.append(
                                                    f"{path or 'root'}: expected {expected}, got {type(data).__name__}"
                              )
            if expected == "object" and "properties" in schema and isinstance(data, dict):
                              for prop, prop_schema in schema["properties"].items():
                                                    if prop in data:
                                                                              self._validate_recursive(
                                                                                                            data[prop], prop_schema, f"{path}.{prop}" if path else prop, errors
                                                                                )
elif schema.get("required") and prop in schema["required"]:
                        errors.append(f"{path}.{prop}: required field missing")
elif isinstance(schema, dict):
            if isinstance(data, dict):
                              for key, sub_schema in schema.items():
                    if key in data:
                                              self._validate_recursive(
                                                                            data[key], sub_schema, f"{path}.{key}" if path else key, errors
                                              )

    @staticmethod
    def merge(*configs: Dict[str, Any]) -> Dict[str, Any]:
              """Deep merge multiple config dicts. Later configs take priority."""
        result: Dict[str, Any] = {}
        for config in configs:
                      result = ConfigManager._deep_merge(result, config)
        return result

    @staticmethod
    def _deep_merge(base: Dict, overlay: Dict) -> Dict:
              """Recursively merge overlay into base."""
              merged = base.copy()
        for key, value in overlay.items():
                      if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                                        merged[key] = ConfigManager._deep_merge(merged[key], value)
else:
                merged[key] = value
        return merged

    @property
    def data(self) -> Dict[str, Any]:
              return self._data

    def __repr__(self) -> str:
              return f"ConfigManager(keys={list(self._data.keys())})"


def main():
      """CLI interface for the config manager."""
    if len(sys.argv) < 2:
              print(__doc__)
        sys.exit(0)

    args = sys.argv[1:]

    # Handle --merge mode
    if "--merge" in args:
              merge_idx = args.index("--merge")
        input_files = args[:merge_idx]
        output_file = args[merge_idx + 1] if merge_idx + 1 < len(args) else None
        if len(input_files) < 2 or not output_file:
                      print("Usage: script.py base.json overlay.json --merge output.json")
            sys.exit(1)
        configs = []
        for f in input_files:
                      with open(f, "r") as fh:
                                        configs.append(json.load(fh))
        merged = ConfigManager.merge(*configs)
        with open(output_file, "w") as fh:
                      json.dump(merged, fh, indent=2)
        print(f"Merged {len(input_files)} configs -> {output_file}")
        sys.exit(0)

    config_file = args[0]
    mgr = ConfigManager(config_file)

    if "--get" in args:
              key = args[args.index("--get") + 1]
        value = mgr.get(key)
        print(json.dumps(value, indent=2) if isinstance(value, (dict, list)) else value)
elif "--set" in args:
        idx = args.index("--set")
        key, raw_value = args[idx + 1], args[idx + 2]
        try:
                      value = json.loads(raw_value)
except json.JSONDecodeError:
            value = raw_value
        mgr.set(key, value)
        mgr.save()
                  print(f"Set {key} = {value!r}")
elif "--delete" in args:
        key = args[args.index("--delete") + 1]
        if mgr.delete(key):
                      mgr.save()
            print(f"Deleted key: {key}")
else:
            print(f"Key not found: {key}")
elif "--validate" in args:
        schema_file = args[args.index("--validate") + 1]
        with open(schema_file, "r") as f:
                      schema = json.load(f)
        errors = mgr.validate(schema)
        if errors:
                      print("Validation errors:")
            for err in errors:
                              print(f"  - {err}")
            sys.exit(1)
        print("Config is valid.")
elif "--env" in args:
        mgr.interpolate_env()
        mgr.save()
        print("Environment variables interpolated and saved.")
else:
        print(json.dumps(mgr.data, indent=2))


if __name__ == "__main__":
      main()
