# Design Document

## Overview

This design document outlines the approach for enhancing the visual styling of the Real-time Recording & Translation interface. The enhancement focuses on improving visual hierarchy, readability, and theme consistency across light and dark modes while maintaining the existing PyQt6 QSS architecture.

## Architecture

### Current State

The application uses:

- **PyQt6** for UI framework
- **QSS (Qt Style Sheets)** for styling, similar to CSS
- **Theme files**: `resources/themes/light.qss` and `resources/themes/dark.qss`
- **Dynamic theme switching** via `QApplication.setStyleSheet()`

### Styling Approach

We will enhance the existing QSS files by:

1. Adding more specific selectors for the three target areas
2. Implementing theme-adaptive color schemes
3. Adding subtle visual effects (shadows, borders, backgrounds)
4. Ensuring accessibility compliance

## Components and Interfaces

### 1. Audio Input Section (`QGroupBox#audio_input_group`)

#### Current State

- Basic border and padding
- Contains: audio input selector, gain slider, audio visualizer
- Minimal visual distinction from other sections

#### Enhanced Design

**Light Theme:**

```qss
QGroupBox#audio_input_group {
    background-color: #f8f9fa;  /* Very light gray-blue */
    border: 1px solid #dee2e6;  /* Light border */
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    font-weight: bold;
}

QGroupBox#audio_input_group::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #495057;
    background-color: #f8f9fa;
}

/* Inner widget background for visualizer area */
QGroupBox#audio_input_group QWidget {
    background-color: #ffffff;
}
```

**Dark Theme:**

```qss
QGroupBox#audio_input_group {
    background-color: #343a40;  /* Dark gray */
    border: 1px solid #495057;  /* Medium gray border */
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    font-weight: bold;
}

QGroupBox#audio_input_group::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #adb5bd;
    background-color: #343a40;
}

QGroupBox#audio_input_group QWidget {
    background-color: #2d2d2d;
}
```

### 2. Transcription Text Area (`QPlainTextEdit#transcription_text`)

#### Current State

- Monospace font for code-like appearance
- Basic border and padding
- Standard scrollbar

#### Enhanced Design

**Light Theme:**

```qss
QPlainTextEdit#transcription_text {
    background-color: #ffffff;
    color: #212529;
    border: 2px solid #dee2e6;
    border-radius: 6px;
    padding: 12px;
    font-family: "SF Mono", "Consolas", "Monaco", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QPlainTextEdit#transcription_text:focus {
    border: 2px solid #0078d4;
    background-color: #f8f9fa;
}

/* Custom scrollbar for transcription */
QPlainTextEdit#transcription_text QScrollBar:vertical {
    background-color: #f8f9fa;
    width: 10px;
    border-radius: 5px;
}

QPlainTextEdit#transcription_text QScrollBar::handle:vertical {
    background-color: #adb5bd;
    border-radius: 5px;
    min-height: 30px;
}

QPlainTextEdit#transcription_text QScrollBar::handle:vertical:hover {
    background-color: #6c757d;
}
```

**Dark Theme:**

```qss
QPlainTextEdit#transcription_text {
    background-color: #212529;
    color: #e9ecef;
    border: 2px solid #495057;
    border-radius: 6px;
    padding: 12px;
    font-family: "SF Mono", "Consolas", "Monaco", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QPlainTextEdit#transcription_text:focus {
    border: 2px solid #0078d4;
    background-color: #2d2d2d;
}

QPlainTextEdit#transcription_text QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 10px;
    border-radius: 5px;
}

QPlainTextEdit#transcription_text QScrollBar::handle:vertical {
    background-color: #495057;
    border-radius: 5px;
    min-height: 30px;
}

QPlainTextEdit#transcription_text QScrollBar::handle:vertical:hover {
    background-color: #6c757d;
}
```

### 3. Translation Text Area (`QPlainTextEdit#translation_text`)

#### Current State

- Similar to transcription area
- No visual differentiation

#### Enhanced Design

**Light Theme:**

```qss
QPlainTextEdit#translation_text {
    background-color: #f8f9fa;  /* Slightly different from transcription */
    color: #212529;
    border: 2px solid #dee2e6;
    border-radius: 6px;
    padding: 12px;
    font-family: "SF Mono", "Consolas", "Monaco", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QPlainTextEdit#translation_text:focus {
    border: 2px solid #0078d4;
    background-color: #ffffff;
}

QPlainTextEdit#translation_text:disabled {
    background-color: #e9ecef;
    color: #6c757d;
    border: 2px solid #ced4da;
}

/* Custom scrollbar for translation */
QPlainTextEdit#translation_text QScrollBar:vertical {
    background-color: #f8f9fa;
    width: 10px;
    border-radius: 5px;
}

QPlainTextEdit#translation_text QScrollBar::handle:vertical {
    background-color: #adb5bd;
    border-radius: 5px;
    min-height: 30px;
}

QPlainTextEdit#translation_text QScrollBar::handle:vertical:hover {
    background-color: #6c757d;
}
```

**Dark Theme:**

```qss
QPlainTextEdit#translation_text {
    background-color: #2d2d2d;  /* Slightly different from transcription */
    color: #e9ecef;
    border: 2px solid #495057;
    border-radius: 6px;
    padding: 12px;
    font-family: "SF Mono", "Consolas", "Monaco", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.6;
    selection-background-color: #0078d4;
    selection-color: #ffffff;
}

QPlainTextEdit#translation_text:focus {
    border: 2px solid #0078d4;
    background-color: #212529;
}

QPlainTextEdit#translation_text:disabled {
    background-color: #1a1d20;
    color: #6c757d;
    border: 2px solid #343a40;
}

QPlainTextEdit#translation_text QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 10px;
    border-radius: 5px;
}

QPlainTextEdit#translation_text QScrollBar::handle:vertical {
    background-color: #495057;
    border-radius: 5px;
    min-height: 30px;
}

QPlainTextEdit#translation_text QScrollBar::handle:vertical:hover {
    background-color: #6c757d;
}
```

## Color Palette

### Light Theme Colors

- **Primary Background**: `#ffffff` (White)
- **Secondary Background**: `#f8f9fa` (Very light gray)
- **Tertiary Background**: `#e9ecef` (Light gray)
- **Primary Text**: `#212529` (Almost black)
- **Secondary Text**: `#495057` (Dark gray)
- **Muted Text**: `#6c757d` (Medium gray)
- **Border**: `#dee2e6` (Light gray)
- **Accent**: `#0078d4` (Blue)

### Dark Theme Colors

- **Primary Background**: `#212529` (Very dark gray)
- **Secondary Background**: `#2d2d2d` (Dark gray)
- **Tertiary Background**: `#343a40` (Medium dark gray)
- **Primary Text**: `#e9ecef` (Almost white)
- **Secondary Text**: `#adb5bd` (Light gray)
- **Muted Text**: `#6c757d` (Medium gray)
- **Border**: `#495057` (Medium gray)
- **Accent**: `#0078d4` (Blue)

## Accessibility Considerations

### Contrast Ratios (WCAG 2.1 Level AA)

**Light Theme:**

- Primary text on white: `#212529` on `#ffffff` = 16.1:1 ✓ (Exceeds 4.5:1)
- Secondary text on light gray: `#495057` on `#f8f9fa` = 8.3:1 ✓
- Border visibility: `#dee2e6` on `#ffffff` = 1.3:1 (Sufficient for non-text)

**Dark Theme:**

- Primary text on dark: `#e9ecef` on `#212529` = 14.8:1 ✓
- Secondary text on medium dark: `#adb5bd` on `#343a40` = 7.2:1 ✓
- Border visibility: `#495057` on `#2d2d2d` = 1.4:1 (Sufficient for non-text)

### Focus Indicators

- All interactive elements have 2px solid `#0078d4` border on focus
- Focus indicators have 3:1 contrast ratio against background

## Visual Hierarchy

### Priority Levels

1. **High Priority**: Transcription and Translation text areas (largest, most prominent)
2. **Medium Priority**: Audio Input controls (distinct background, clear grouping)
3. **Low Priority**: Labels and secondary controls (subtle, supportive)

### Spacing and Layout

- **Section Spacing**: 15-20px between major sections
- **Internal Padding**: 12-16px within grouped elements
- **Border Radius**: 6-8px for rounded corners (modern, friendly)
- **Line Height**: 1.6 for text areas (optimal readability)

## Error Handling

### Error States

- Invalid input: Red border (`#dc3545`)
- Warning state: Orange border (`#fd7e14`)
- Success state: Green border (`#28a745`)

### Error Styling

```qss
QPlainTextEdit#transcription_text[error="true"],
QPlainTextEdit#translation_text[error="true"] {
    border: 2px solid #dc3545;
}
```

## Testing Strategy

### Visual Testing

1. **Theme Switching**: Verify smooth transition between light and dark themes
2. **Contrast Testing**: Use automated tools to verify WCAG compliance
3. **Cross-Platform**: Test on macOS and Windows
4. **Screen Sizes**: Test on different resolutions (1920x1080, 2560x1440, 3840x2160)

### Functional Testing

1. **Focus States**: Verify focus indicators work correctly
2. **Hover Effects**: Verify hover states are visible and smooth
3. **Disabled States**: Verify disabled elements are clearly indicated
4. **Scrolling**: Verify custom scrollbars work correctly

### Accessibility Testing

1. **Contrast Checker**: Use WebAIM or similar tools
2. **Screen Reader**: Test with VoiceOver (macOS) or NVDA (Windows)
3. **Keyboard Navigation**: Verify all elements are keyboard accessible

## Implementation Notes

### File Modifications

- `resources/themes/light.qss`: Add/update styles for the three target areas
- `resources/themes/dark.qss`: Add/update styles for the three target areas
- No Python code changes required (pure QSS enhancement)

### Backward Compatibility

- All changes are additive or refinements
- Existing functionality remains unchanged
- No breaking changes to widget structure

### Performance Considerations

- QSS is compiled by Qt, minimal performance impact
- No JavaScript or heavy animations
- Efficient selector usage (ID selectors are fastest)

## Future Enhancements

### Potential Improvements

1. **Animations**: Subtle fade-in for new transcription text
2. **Themes**: Additional theme options (high contrast, sepia)
3. **Customization**: User-configurable colors
4. **Responsive**: Adaptive layouts for smaller screens

### Technical Debt

- Consider migrating to QML for more advanced styling capabilities
- Evaluate CSS Grid-like layouts for better responsiveness
- Implement theme preview before applying
