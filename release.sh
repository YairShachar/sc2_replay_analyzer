#!/bin/bash
set -e

# Get current version
CURRENT=$(grep 'version = ' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
echo "Current version: $CURRENT"

# Ask for new version
read -p "New version: " VERSION
if [ -z "$VERSION" ]; then
    echo "No version provided. Aborting."
    exit 1
fi

# Update versions
sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/sc2_replay_analyzer/__init__.py

echo "Building..."
rm -rf dist/
python -m build

echo "Uploading to PyPI..."
twine upload dist/*

echo "Creating git release..."
git add .
git commit -m "Release v$VERSION"
git branch "release/$VERSION"

echo ""
echo "✓ Released v$VERSION"
echo "  Branch: release/$VERSION"
echo "  PyPI: https://pypi.org/project/sc2-replay-analyzer/$VERSION/"
