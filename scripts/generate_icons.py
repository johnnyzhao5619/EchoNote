#!/usr/bin/env python3
"""
Icon generation script for EchoNote.

This script generates platform-specific icon formats from the main PNG logo.
Requires: Pillow (for ICO generation), macOS sips and iconutil (for ICNS)
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required for ICO generation")
    print("Install with: pip install Pillow")
    sys.exit(1)


def generate_icns(source_png: Path, output_icns: Path) -> bool:
    """Generate macOS ICNS file from PNG source."""
    if sys.platform != "darwin":
        print("Warning: ICNS generation requires macOS")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        iconset_dir = Path(temp_dir) / "echonote.iconset"
        iconset_dir.mkdir()

        # Generate all required sizes
        sizes = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]

        for size, filename in sizes:
            cmd = [
                "sips",
                "-z",
                str(size),
                str(size),
                str(source_png),
                "--out",
                str(iconset_dir / filename),
            ]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                print(f"Error generating {filename}: {result.stderr.decode()}")
                return False

        # Create ICNS file
        cmd = ["iconutil", "-c", "icns", str(iconset_dir), "--output", str(output_icns)]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"Error creating ICNS: {result.stderr.decode()}")
            return False

    return True


def generate_ico(source_png: Path, output_ico: Path) -> bool:
    """Generate Windows ICO file from PNG source."""
    try:
        img = Image.open(source_png)

        # Create different sizes for ICO
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        ico_images = []

        for size in sizes:
            resized = img.resize(size, Image.Resampling.LANCZOS)
            ico_images.append(resized)

        # Save as ICO
        ico_images[0].save(
            output_ico, format="ICO", sizes=[(img.width, img.height) for img in ico_images]
        )
        return True

    except Exception as e:
        print(f"Error generating ICO: {e}")
        return False


def main():
    """Generate all platform-specific icons."""
    project_root = Path(__file__).parent.parent
    icons_dir = project_root / "resources" / "icons"

    source_png = icons_dir / "echonote.png"
    if not source_png.exists():
        print(f"Error: Source PNG not found at {source_png}")
        sys.exit(1)

    print(f"Generating icons from {source_png}")

    # Generate ICNS for macOS
    icns_path = icons_dir / "echonote.icns"
    if generate_icns(source_png, icns_path):
        print(f"✓ Generated {icns_path}")
    else:
        print(f"✗ Failed to generate {icns_path}")

    # Generate ICO for Windows
    ico_path = icons_dir / "echonote.ico"
    if generate_ico(source_png, ico_path):
        print(f"✓ Generated {ico_path}")
    else:
        print(f"✗ Failed to generate {ico_path}")

    print("\nIcon generation complete!")
    print("\nGenerated files:")
    for icon_file in ["echonote.png", "echonote.icns", "echonote.ico"]:
        path = icons_dir / icon_file
        if path.exists():
            size = path.stat().st_size
            print(f"  {icon_file}: {size:,} bytes")


if __name__ == "__main__":
    main()
