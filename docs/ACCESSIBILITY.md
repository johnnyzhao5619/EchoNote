# EchoNote Accessibility Guide

## Overview

EchoNote is designed to be accessible to all users, including those with disabilities. This guide outlines the accessibility features available in the application.

## Keyboard Navigation

### Global Shortcuts

- **Ctrl+1**: Switch to Batch Transcribe page
- **Ctrl+2**: Switch to Real-time Record page
- **Ctrl+3**: Switch to Calendar Hub page
- **Ctrl+4**: Switch to Timeline page
- **Ctrl+5**: Switch to Settings page
- **Ctrl+,**: Open Settings (alternative)
- **Ctrl+Q**: Quit application

### Tab Navigation

All interactive elements in EchoNote can be accessed using the Tab key:

- **Tab**: Move to next focusable element
- **Shift+Tab**: Move to previous focusable element
- **Enter/Space**: Activate focused button or control
- **Arrow Keys**: Navigate within lists, combo boxes, and other controls

### Focus Indicators

All focusable elements display a clear visual indicator when focused:

- Blue outline in Light and Dark themes
- Cyan outline in High Contrast theme
- Increased border width for better visibility

## Screen Reader Support

EchoNote provides comprehensive screen reader support through:

### Accessible Names

All interactive elements have descriptive accessible names that screen readers can announce:

- Buttons describe their action (e.g., "Start Recording", "Import File")
- Input fields describe their purpose (e.g., "Source Language", "Audio Gain")
- Status indicators announce their current state

### Accessible Descriptions

Complex controls include additional descriptions to help users understand their purpose and usage.

### Live Regions

Dynamic content updates are announced to screen readers:

- Transcription progress updates
- Recording status changes
- Task completion notifications
- Error messages

## High Contrast Mode

EchoNote includes a dedicated High Contrast theme for users with visual impairments:

### Activating High Contrast Mode

1. Open Settings (Ctrl+5 or Ctrl+,)
2. Navigate to Appearance section
3. Select "High Contrast" from the Theme dropdown
4. Changes apply immediately

### High Contrast Features

- **Maximum Contrast**: Black background with white text and yellow highlights
- **Bold Borders**: 3-4px borders for all interactive elements
- **Large Focus Indicators**: Cyan outlines with 3px width
- **Clear Visual Hierarchy**: Distinct colors for different element states
  - Yellow: Primary actions and selected items
  - White: Secondary actions and borders
  - Cyan: Focus indicators
  - Red: Error states

## Visual Accessibility

### Font Sizes

- Base font size: 14px
- Page titles: 20-22px
- Section titles: 16-18px
- All text is scalable with system font size settings

### Color Contrast

All themes meet WCAG 2.1 Level AA contrast requirements:

- Light theme: 4.5:1 minimum contrast ratio
- Dark theme: 4.5:1 minimum contrast ratio
- High Contrast theme: 7:1+ contrast ratio

### Color Independence

Information is never conveyed by color alone:

- Status indicators include text labels
- Buttons include text descriptions
- Icons are accompanied by labels

## Motor Accessibility

### Large Click Targets

All interactive elements meet minimum size requirements:

- Buttons: Minimum 36x36px
- Checkboxes/Radio buttons: 22x22px
- Combo boxes: Minimum 42px height
- Sliders: 22px handle size

### Keyboard-Only Operation

Every feature in EchoNote can be accessed without a mouse:

- Full keyboard navigation support
- Keyboard shortcuts for common actions
- No mouse-only interactions

### Reduced Motion

EchoNote respects system reduced motion preferences:

- Animations can be disabled system-wide
- Essential animations are kept minimal
- No auto-playing animations

## Cognitive Accessibility

### Clear Language

- Simple, direct language throughout the interface
- Consistent terminology
- Helpful error messages with suggested solutions

### Predictable Behavior

- Consistent navigation structure
- Standard UI patterns
- Clear feedback for all actions

### Error Prevention

- Confirmation dialogs for destructive actions
- Input validation with clear error messages
- Undo capabilities where appropriate

## Testing Accessibility

### Screen Reader Testing

EchoNote has been tested with:

- **Windows**: NVDA, JAWS
- **macOS**: VoiceOver
- **Linux**: Orca

### Keyboard Navigation Testing

All features have been verified to work with keyboard-only navigation.

### High Contrast Testing

The High Contrast theme has been tested with various visual impairments in mind.

## Reporting Accessibility Issues

If you encounter any accessibility barriers while using EchoNote, please report them:

1. Open an issue on our GitHub repository
2. Include:
   - Description of the barrier
   - Steps to reproduce
   - Your assistive technology (if applicable)
   - Operating system and version

We are committed to making EchoNote accessible to everyone and will address reported issues promptly.

## Future Improvements

We are continuously working to improve accessibility:

- [ ] Voice control support
- [ ] Customizable keyboard shortcuts
- [ ] Adjustable font sizes in settings
- [ ] Additional theme options
- [ ] Improved screen reader announcements
- [ ] Braille display support

## Resources

### Accessibility Standards

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Qt Accessibility](https://doc.qt.io/qt-6/accessible.html)

### Assistive Technologies

- [NVDA Screen Reader](https://www.nvaccess.org/)
- [JAWS Screen Reader](https://www.freedomscientific.com/products/software/jaws/)
- [VoiceOver (macOS)](https://www.apple.com/accessibility/voiceover/)
- [Orca Screen Reader (Linux)](https://help.gnome.org/users/orca/stable/)

## Contact

For accessibility-related questions or feedback:

- Email: accessibility@echonote.app
- GitHub Issues: [EchoNote Issues](https://github.com/echonote/echonote/issues)

---

Last Updated: October 2025
