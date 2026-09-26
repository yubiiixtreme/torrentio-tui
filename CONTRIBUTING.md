# Contributing to Torrentio TUI

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## 🚀 Quick Start

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/torrentio-tui.git
   cd torrentio-tui
   ```
3. **Create a virtual environment** and install in development mode:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/amazing-feature
   ```

## 🧪 Running Tests

```bash
# Run all tests
pytest -q

# Run with coverage
pytest --cov=torrentio_tui --cov-report=term-missing

# Run a specific test file
pytest tests/test_stremio_source.py -v
```

## ✨ Code Style

This project uses **Ruff** for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .

# Check formatting without changes
ruff format --check .
```

The CI pipeline runs these checks automatically on every PR.

## 📝 Commit Messages

Follow conventional commits format:
- `feat: add new feature`
- `fix: bug fix`
- `docs: documentation changes`
- `style: formatting, missing semi colons, etc`
- `refactor: refactoring production code`
- `test: adding missing tests, refactoring tests`
- `chore: updating build tasks, package manager configs`

Example:
```
feat: add poster art support to detail panel

- Download and display poster images from Cinemeta
- Add async loading with fallback placeholder
- Update CSS for poster container styling
```

## 🏗 Adding a New Source

1. Copy `torrentio_tui/sources/example.py` to `torrentio_tui/sources/yoursource.py`
2. Implement the `Source` ABC: `search()`, `get_episodes()`, `get_streams()`
3. Register in `torrentio_tui/sources/registry.py`
4. Add tests in `tests/`
5. Update README if needed

See [Sources](#sources) in README for details.

## 🎨 UI Contributions

The TUI is built with **Textual**. Key files:
- `torrentio_tui/ui/app.tcss` — all styling (CSS-like)
- `torrentio_tui/ui/screens/` — screen layouts
- `torrentio_tui/ui/app.py` — main app class

When modifying CSS:
- Test with different terminal sizes
- Respect `prefers-reduced-motion`
- Use CSS custom properties (defined in `:root`)
- Keep animations subtle and purposeful

## 🔧 Configuration

User config lives at `~/.config/torrentio-tui/config.toml`. When adding new config options:
1. Add to `DEFAULT_CONFIG_TOML` in `torrentio_tui/config.py`
2. Add corresponding dataclass field
3. Handle env var override in `Config.load()`
4. Document in README

## 📦 Releasing

Releases are automated via GitHub Actions when a version tag is pushed:

```bash
# Update version in pyproject.toml
# Update CHANGELOG.md (if exists)
git commit -am "chore: release v0.3.0"
git tag v0.3.0
git push origin main --tags
```

The CI will build and publish to PyPI automatically.

## 📋 Pull Request Checklist

Before submitting a PR, ensure:
- [ ] Tests pass locally (`pytest -q`)
- [ ] Code passes linting (`ruff check .`)
- [ ] Code is formatted (`ruff format --check .`)
- [ ] New features have tests
- [ ] Documentation updated if needed
- [ ] Commit messages follow convention
- [ ] PR description explains the change and why

## 💬 Getting Help

- Open a GitHub Discussion for questions
- Check existing Issues before creating new ones
- Be respectful and constructive in all interactions

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.