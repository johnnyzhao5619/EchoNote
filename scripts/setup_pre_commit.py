#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Pre-commit hooks setup for EchoNote quality checks.

This script sets up pre-commit hooks that run quality checks before each commit.
"""

import os
import subprocess
import sys
from pathlib import Path

def create_pre_commit_config():
    """Create or update .pre-commit-config.yaml with quality checks."""
    config_content = """# Pre-commit hooks for EchoNote code quality
repos:
  # Code formatting
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3
        args: [--line-length=100]

  # Import sorting
  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile=black, --line-length=100]

  # Linting
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=100, --extend-ignore=E203,W503]

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
        args: [--ignore-missing-imports]

  # Security scanning
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, -f, json]
        exclude: ^tests/

  # General hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=1000]

  # Custom hooks for EchoNote
  - repo: local
    hooks:
      - id: i18n-check
        name: Check internationalization
        entry: python scripts/analyze_i18n.py
        language: system
        args: [--format=json, --output-dir=.pre-commit-reports]
        pass_filenames: false
        files: '^(ui|core|engines|utils)/.*\.py$'

      - id: complexity-check
        name: Check code complexity
        entry: python scripts/check_complexity.py
        language: system
        pass_filenames: true
        files: '\.py$'
"""

    config_file = Path(".pre-commit-config.yaml")
    with open(config_file, 'w') as f:
        f.write(config_content)

    print(f"✅ Created {config_file}")

def create_complexity_checker():
    """Create a simple complexity checker for pre-commit."""
    checker_content = '''#!/usr/bin/env python3
"""
Simple complexity checker for pre-commit hooks.
"""

import ast
import sys
from pathlib import Path

def check_complexity(file_path, max_complexity=10):
    """Check if file has functions with complexity above threshold."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = calculate_complexity(node)
                if complexity > max_complexity:
                    issues.append(f"{file_path}:{node.lineno}: Function '{node.name}' has complexity {complexity} (max: {max_complexity})")

        return issues

    except Exception as e:
        return [f"{file_path}: Error analyzing file: {e}"]

def calculate_complexity(node):
    """Calculate cyclomatic complexity for a function."""
    complexity = 1  # Base complexity

    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1

    return complexity

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: check_complexity.py <file1> [file2] ...")
        sys.exit(1)

    all_issues = []

    for file_path in sys.argv[1:]:
        if Path(file_path).suffix == '.py':
            issues = check_complexity(file_path)
            all_issues.extend(issues)

    if all_issues:
        print("Complexity issues found:")
        for issue in all_issues:
            print(f"  {issue}")
        sys.exit(1)
    else:
        print("✅ All files pass complexity check")

if __name__ == "__main__":
    main()
'''

    checker_file = Path("scripts/check_complexity.py")
    with open(checker_file, 'w') as f:
        f.write(checker_content)

    # Make executable
    os.chmod(checker_file, 0o755)
    print(f"✅ Created {checker_file}")

def install_pre_commit():
    """Install pre-commit if not already installed."""
    try:
        subprocess.run(['pre-commit', '--version'], check=True, capture_output=True)
        print("✅ pre-commit is already installed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("📦 Installing pre-commit...")
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pre-commit'], check=True)
            print("✅ pre-commit installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install pre-commit: {e}")
            return False

    return True

def setup_pre_commit_hooks():
    """Set up pre-commit hooks in the repository."""
    try:
        subprocess.run(['pre-commit', 'install'], check=True)
        print("✅ Pre-commit hooks installed")

        # Install commit-msg hook for conventional commits
        subprocess.run(['pre-commit', 'install', '--hook-type', 'commit-msg'], check=True)
        print("✅ Commit message hooks installed")

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install pre-commit hooks: {e}")
        return False

def test_pre_commit():
    """Test pre-commit hooks on all files."""
    print("🧪 Testing pre-commit hooks...")
    try:
        result = subprocess.run(['pre-commit', 'run', '--all-files'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ All pre-commit hooks passed")
        else:
            print("⚠️  Some pre-commit hooks failed (this is normal for first run)")
            print("Run 'pre-commit run --all-files' to see details")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to test pre-commit hooks: {e}")
        return False

def main():
    """Main setup function."""
    print("🔧 Setting up pre-commit hooks for EchoNote")
    print("=" * 50)

    # Create reports directory
    reports_dir = Path(".pre-commit-reports")
    reports_dir.mkdir(exist_ok=True)
    print(f"📁 Created reports directory: {reports_dir}")

    # Create configuration files
    create_pre_commit_config()
    create_complexity_checker()

    # Install pre-commit
    if not install_pre_commit():
        sys.exit(1)

    # Set up hooks
    if not setup_pre_commit_hooks():
        sys.exit(1)

    # Test hooks
    test_pre_commit()

    print("\n✅ Pre-commit setup complete!")
    print("\nNext steps:")
    print("1. Run 'pre-commit run --all-files' to check all files")
    print("2. Commit changes to activate hooks")
    print("3. Hooks will now run automatically on each commit")

if __name__ == "__main__":
    main()
'''