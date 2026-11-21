#!/usr/bin/env python3
"""Config Enforcer.

Compares each config in current/ against its golden baseline in golden/.

Exit codes:
    0 = all configs compliant
    1 = violations detected (deployment blocked)
    2 = error (missing files, bad YAML, etc.)

Usage (run from ~/golden-config-lab):
    python3 scripts/config_enforcer.py
"""

import sys
from datetime import datetime
from pathlib import Path

import yaml


class ConfigEnforcer:
    """Compare current configurations against golden standards."""

    def __init__(self, golden_dir='golden', current_dir='current', log_dir='logs'):
        self.golden_dir = Path(golden_dir)
        self.current_dir = Path(current_dir)
        self.log_dir = Path(log_dir)
        self.violations = []

    def load_yaml(self, filepath):
        """Load a YAML file and return it as a dictionary."""
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)
            return data if data is not None else {}
        except FileNotFoundError:
            print(f"ERROR: file not found: {filepath}")
            sys.exit(2)
        except yaml.YAMLError as e:
            print(f"ERROR: invalid YAML in {filepath}: {e}")
            sys.exit(2)

    def compare_values(self, golden, current, path, config_name):
        """Recursively check that current satisfies every golden value."""
        if isinstance(golden, dict):
            if not isinstance(current, dict):
                self.add_violation(config_name, path,
                                   "expected a mapping", current)
                return
            for key, golden_value in golden.items():
                key_path = f"{path}.{key}" if path else str(key)
                if key not in current:
                    self.add_violation(config_name, key_path,
                                       golden_value, "<missing>")
                else:
                    self.compare_values(golden_value, current[key],
                                        key_path, config_name)
        elif golden != current:
            self.add_violation(config_name, path, golden, current)

    def add_violation(self, config_name, path, expected, actual):
        self.violations.append({
            'config': config_name,
            'path': path,
            'expected': expected,
            'actual': actual,
        })

    def compare_configs(self, golden_config, current_config, config_name):
        """Compare current config against golden standard."""
        before = len(self.violations)
        self.compare_values(golden_config, current_config, '', config_name)
        return self.violations[before:]

    def find_current_files(self, config_name):
        """Find current files for a service, e.g. ssh -> ssh_*.yaml."""
        return sorted(self.current_dir.glob(f"{config_name}_*.yaml"))

    def run(self):
        """Check every golden config against its current file(s)."""
        golden_files = sorted(self.golden_dir.glob('*_golden.yaml'))
        if not golden_files:
            print(f"ERROR: no *_golden.yaml files in {self.golden_dir}/")
            return 2

        checked = 0
        for golden_file in golden_files:
            config_name = golden_file.name[:-len('_golden.yaml')]
            golden_config = self.load_yaml(golden_file)

            current_files = self.find_current_files(config_name)
            if not current_files:
                print(f"SKIP: no current config found for '{config_name}'")
                continue

            for current_file in current_files:
                current_config = self.load_yaml(current_file)
                found = self.compare_configs(golden_config, current_config,
                                             config_name)
                checked += 1
                status = "FAIL" if found else "PASS"
                print(f"[{status}] {current_file.name} vs {golden_file.name}")
                for v in found:
                    print(f"    - {v['path']}: expected {v['expected']!r}, "
                          f"got {v['actual']!r}")

        self.write_log()

        if checked == 0:
            print("ERROR: nothing was checked")
            return 2

        if self.violations:
            print(f"\nViolations detected: {len(self.violations)}. "
                  f"Deployment blocked.")
            return 1

        print("\nNo violations. Configurations are compliant.")
        return 0

    def write_log(self):
        """Write results to logs/ with a timestamp."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f"enforcer_{stamp}.log"
        with open(log_file, 'w') as f:
            f.write(f"Config enforcer run: {datetime.now().isoformat()}\n")
            f.write(f"Violations: {len(self.violations)}\n")
            for v in self.violations:
                f.write(f"{v['config']} | {v['path']} | "
                        f"expected={v['expected']!r} | actual={v['actual']!r}\n")


def main():
    enforcer = ConfigEnforcer()
    sys.exit(enforcer.run())


if __name__ == '__main__':
    main()
