# SC2 Replay Analyzer - Development Guidelines

## Commit Message Conventions

Use these prefixes to enable automatic version suggestions in `release.sh`:

| Prefix | Version Bump | Example |
|--------|--------------|---------|
| `feat:` | Minor (0.1.0 → 0.2.0) | `feat: add configurable columns` |
| `fix:` | Patch (0.1.0 → 0.1.1) | `fix: correct time scale calculation` |
| `breaking:` or `!:` | Major (0.1.0 → 1.0.0) | `breaking: change config format` |

Other prefixes (no version bump suggestion):
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

## Running Tests

```bash
python -m pytest tests/ -v
```

## Releasing

```bash
./release.sh
```

The script will:
1. Suggest version based on commit messages
2. Generate release notes from commits
3. Build and upload to PyPI
4. Create git release branch
