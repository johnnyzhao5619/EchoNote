# Settings UI Quick Reference

## Usage

### Basic Integration

```python
from ui.settings import SettingsWidget
from core.settings.manager import SettingsManager
from utils.i18n import I18nQtManager

# Initialize managers
settings_manager = SettingsManager(config_manager)
i18n = I18nQtManager()

# Create settings widget
settings_widget = SettingsWidget(
    settings_manager,
    i18n,
    managers={
        'settings_manager': settings_manager,
        'security_manager': security_manager,  # Optional
        'usage_tracker': usage_tracker,        # Optional
        'main_window': main_window,            # Optional
    }
)

# Connect signals
settings_widget.settings_saved.connect(on_settings_saved)

# Show widget
settings_widget.show()
```

### Adding to Main Window

```python
# In MainWindow.setup_ui()
from ui.settings import SettingsWidget

settings_widget = SettingsWidget(
    self.managers['settings_manager'],
    self.i18n,
    self.managers
)

# Add to main window
self.add_page('settings', settings_widget)
```

## Settings Categories

### 1. Transcription Settings

- **Path**: `transcription.*`
- **Key Settings**:
  - `default_output_format`: txt/srt/md
  - `max_concurrent_tasks`: 1-5
  - `default_save_path`: string
  - `default_engine`: faster-whisper/openai/google/azure
  - `faster_whisper.model_size`: tiny/base/small/medium/large
  - `faster_whisper.device`: cpu/cuda
  - `faster_whisper.compute_type`: int8/float16/float32

### 2. Realtime Settings

- **Path**: `realtime.*`
- **Key Settings**:
  - `default_input_source`: default/system
  - `default_gain`: 0.1-2.0
  - `recording_format`: wav/mp3
  - `recording_save_path`: string
  - `auto_save`: boolean

### 3. Calendar Settings

- **Path**: `calendar.*`
- **Key Settings**:
  - Connected accounts managed in database
  - No direct settings in config

### 4. Timeline Settings

- **Path**: `timeline.*`
- **Key Settings**:
  - `past_days`: 1-365
  - `future_days`: 1-365
  - `reminder_minutes`: 5/10/15/30
  - `auto_start_enabled`: boolean

### 5. Appearance Settings

- **Path**: `ui.theme`
- **Values**: light/dark/system

### 6. Language Settings

- **Path**: `ui.language`
- **Values**: en_US

## API Reference

### SettingsWidget

**Methods**:

- `load_settings()`: Load settings from manager
- `save_settings()`: Save settings to manager
- `check_unsaved_changes()`: Check for unsaved changes

**Signals**:

- `settings_saved()`: Emitted when settings are saved

### BaseSettingsPage

**Methods to Override**:

- `load_settings()`: Load settings into UI
- `save_settings()`: Save settings from UI
- `validate_settings()`: Validate settings (returns tuple)
- `update_translations()`: Update UI text after language change

**Helper Methods**:

- `add_section_title(title)`: Add section title
- `add_spacing(height)`: Add vertical spacing
- `_emit_changed()`: Emit settings changed signal

## Validation

Each settings page can implement validation:

```python
def validate_settings(self) -> Tuple[bool, str]:
    """
    Validate settings.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not self.path_edit.text():
        return False, "Path cannot be empty"

    return True, ""
```

## Translation Keys

All text should use translation keys:

```python
# Good
label = QLabel(self.i18n.t('settings.transcription.output_format'))

# Bad
label = QLabel("Output Format")
```

## Common Patterns

### Adding a Setting

1. Add UI widget in `setup_ui()`
2. Connect change signal to `_emit_changed()`
3. Load value in `load_settings()`
4. Save value in `save_settings()`
5. Add validation in `validate_settings()` if needed

### Example:

```python
# In setup_ui()
self.my_setting_edit = QLineEdit()
self.my_setting_edit.textChanged.connect(self._emit_changed)

# In load_settings()
value = self.settings_manager.get_setting('category.my_setting')
if value:
    self.my_setting_edit.setText(value)

# In save_settings()
self.settings_manager.set_setting(
    'category.my_setting',
    self.my_setting_edit.text()
)

# In validate_settings()
if not self.my_setting_edit.text():
    return False, "My setting cannot be empty"
```

## Troubleshooting

### Settings Not Saving

- Check if validation is passing
- Check if SettingsManager.save_settings() is called
- Check file permissions on config file

### UI Not Updating After Language Change

- Ensure `update_translations()` is implemented
- Ensure widget is connected to `language_changed` signal

### Theme Not Applying

- Ensure MainWindow is passed in managers dict
- Ensure MainWindow has `apply_theme()` method

## Best Practices

1. **Always validate user input** before saving
2. **Use translation keys** for all user-facing text
3. **Emit `_emit_changed()`** when settings change
4. **Provide helpful error messages** in validation
5. **Use appropriate widgets** (spinbox for numbers, combo for choices)
6. **Group related settings** with section titles
7. **Add tooltips** for complex settings
8. **Test with different languages** to ensure UI layout works
