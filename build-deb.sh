#!/bin/bash
# Build script for Debai Debian package

set -e

echo "Building Debai Debian package..."

# Check for required tools
command -v dpkg-buildpackage >/dev/null 2>&1 || {
    echo "Error: dpkg-buildpackage not found. Install with:"
    echo "  sudo apt install build-essential debhelper"
    exit 1
}

# Clean previous builds
echo "Cleaning previous builds..."
sudo rm -rf debian/debai debian/debai-doc debian/.debhelper debian/tmp debian/python3-debai
sudo rm -rf .pybuild build dist src/*.egg-info
rm -f debian/files debian/debai.substvars debian/debai-doc.substvars
rm -f ../debai_*.deb ../debai_*.buildinfo ../debai_*.changes

# Build the package
echo "Building package..."
dpkg-buildpackage -us -uc -b

echo ""
echo "Build complete!"
echo "Package: ../debai_1.0.0-1_all.deb"
echo ""
echo "Install with:"
echo "  sudo dpkg -i ../debai_1.0.0-1_all.deb"
echo "  sudo apt-get install -f"
