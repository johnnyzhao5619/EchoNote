# EchoNote Icon Assets

This directory contains the official EchoNote application icons in various formats for different platforms and use cases.

## Icon Files

### Primary Logo

- **`echonote.png`** - Main application icon (1024x1024 PNG)
  - Used in: Application window, README, documentation
  - Format: PNG with transparency (RGBA)
  - Resolution: 1024x1024 pixels
  - Background: Central white background with transparent edges
  - Design: 9.7% white background, 61.5% colored content, 28.8% transparent
  - Features: Circular white background in center for better visibility

### Platform-Specific Icons

- **`echonote.icns`** - macOS application bundle icon
  - Contains multiple resolutions: 16x16 to 1024x1024
  - Used by: PyInstaller for macOS builds
- **`echonote.ico`** - Windows application icon
  - Contains multiple resolutions: 16x16 to 256x256
  - Used by: PyInstaller for Windows builds

### Legacy

- **`Logo.png`** - Original logo file (kept for compatibility)
  - Same as echonote.png but with different naming

## Usage Guidelines

### In Code

```python
# PySide6 application icon
from PySide6.QtGui import QIcon
app.setWindowIcon(QIcon("resources/icons/echonote.png"))
```

### In Documentation

```markdown
![EchoNote Logo](resources/icons/echonote.png)
```

### Build Configuration

The build system automatically selects the appropriate icon format:

- macOS: `echonote.icns`
- Windows: `echonote.ico`
- Linux: `echonote.png`

## Icon Design

The EchoNote icon represents:

- **Audio waves** - Voice transcription capabilities
- **Modern design** - Clean, professional appearance
- **Central white background** - Improves visibility and contrast
- **Transparent edges** - Seamless integration with any UI theme
- **Accessibility** - High contrast, clear at all sizes
- **Brand identity** - Consistent with application theme

### Background Design Features

- **Circular white background** - Central area with white background for better visibility
- **Gradient transparency** - Smooth transition from white center to transparent edges
- **Universal compatibility** - Works well on light, dark, and colored backgrounds
- **Optimal contrast** - White background ensures logo visibility in all contexts

## Regenerating Icons

If you need to update the icons from a new source image:

1. Replace `echonote.png` with your new 1024x1024 PNG
2. Run the icon generation script:

```bash
# macOS ICNS generation
mkdir -p /tmp/echonote.iconset
sips -z 16 16 echonote.png --out /tmp/echonote.iconset/icon_16x16.png
sips -z 32 32 echonote.png --out /tmp/echonote.iconset/icon_16x16@2x.png
sips -z 32 32 echonote.png --out /tmp/echonote.iconset/icon_32x32.png
sips -z 64 64 echonote.png --out /tmp/echonote.iconset/icon_32x32@2x.png
sips -z 128 128 echonote.png --out /tmp/echonote.iconset/icon_128x128.png
sips -z 256 256 echonote.png --out /tmp/echonote.iconset/icon_128x128@2x.png
sips -z 256 256 echonote.png --out /tmp/echonote.iconset/icon_256x256.png
sips -z 512 512 echonote.png --out /tmp/echonote.iconset/icon_256x256@2x.png
sips -z 512 512 echonote.png --out /tmp/echonote.iconset/icon_512x512.png
sips -z 1024 1024 echonote.png --out /tmp/echonote.iconset/icon_512x512@2x.png
iconutil -c icns /tmp/echonote.iconset --output echonote.icns
rm -rf /tmp/echonote.iconset

# Windows ICO generation (requires Pillow)
python -c "
from PIL import Image
img = Image.open('echonote.png')
sizes = [(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]
ico_images = [img.resize(size, Image.Resampling.LANCZOS) for size in sizes]
ico_images[0].save('echonote.ico', format='ICO', sizes=[(img.width, img.height) for img in ico_images])
"
```

## License

These icon assets are part of the EchoNote project and are licensed under the Apache 2.0 License.
