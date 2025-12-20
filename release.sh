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

# Generate release notes from commits
echo ""
echo "Generating release notes..."

# Find last release branch
LAST_RELEASE=$(git branch -a 2>/dev/null | grep 'release/' | sed 's/.*release\///' | sort -V | tail -1)

if [ -n "$LAST_RELEASE" ]; then
    echo "Changes since v$LAST_RELEASE:"
    echo ""
    COMMITS=$(git log "release/$LAST_RELEASE"..HEAD --pretty=format:"- %s" 2>/dev/null || echo "")
else
    echo "Changes (first release):"
    echo ""
    COMMITS=$(git log --pretty=format:"- %s" -20 2>/dev/null || echo "")
fi

if [ -z "$COMMITS" ]; then
    COMMITS="- Initial release"
fi

echo "$COMMITS"
echo ""

# Allow editing release notes
NOTES_FILE=$(mktemp)
echo "$COMMITS" > "$NOTES_FILE"

read -p "Edit release notes in editor? [y/N]: " EDIT_NOTES
if [[ "$EDIT_NOTES" =~ ^[Yy]$ ]]; then
    ${EDITOR:-vim} "$NOTES_FILE"
fi

RELEASE_NOTES=$(cat "$NOTES_FILE")
rm "$NOTES_FILE"

# Update versions
echo ""
echo "Updating version to $VERSION..."
sed -i '' "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/sc2_replay_analyzer/__init__.py

echo "Building..."
rm -rf dist/
python -m build

echo "Uploading to PyPI..."
twine upload dist/*

# Create git release
echo ""
echo "Creating git release..."
git add .
git commit -m "Release v$VERSION

$RELEASE_NOTES"

git branch "release/$VERSION"

# Optionally create GitHub release
read -p "Create GitHub release? [y/N]: " CREATE_GH
if [[ "$CREATE_GH" =~ ^[Yy]$ ]]; then
    if command -v gh &> /dev/null; then
        git push origin HEAD
        git push origin "release/$VERSION"
        gh release create "v$VERSION" --title "v$VERSION" --notes "$RELEASE_NOTES"
        echo "GitHub release created!"
    else
        echo "Warning: gh CLI not installed. Skipping GitHub release."
        echo "Install with: brew install gh"
    fi
fi

echo ""
echo "✓ Released v$VERSION"
echo "  Branch: release/$VERSION"
echo "  PyPI: https://pypi.org/project/sc2-replay-analyzer/$VERSION/"
