"""
First run setup for EchoNote application.

Handles initialization tasks that need to be performed on first run,
including a welcome wizard for initial configuration.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from config.app_config import get_app_dir


logger = logging.getLogger(__name__)


class FirstRunSetup:
    """Handles first-run initialization of the application."""

    @staticmethod
    def is_first_run() -> bool:
        """
        Check if this is the first run of the application.

        Returns:
            True if this is the first run, False otherwise
        """
        config_dir = get_app_dir()
        return not config_dir.exists()

    @staticmethod
    def setup(model_manager=None) -> None:
        """
        Perform first-run initialization.

        Creates necessary directories, copies default configuration,
        initializes database. Model download is now handled separately
        through the model recommendation dialog.

        Args:
            model_manager: Optional ModelManager instance for model
                          recommendation (used after UI is initialized)
        """
        config_dir = get_app_dir()

        try:
            logger.info("Starting first-run setup...")

            # Create main config directory
            config_dir.mkdir(exist_ok=True)
            logger.info(f"Created config directory: {config_dir}")

            # Create subdirectories
            subdirs = ['logs', 'models']
            for subdir in subdirs:
                subdir_path = config_dir / subdir
                subdir_path.mkdir(exist_ok=True)
                logger.info(f"Created subdirectory: {subdir_path}")

            # Copy default configuration file to user directory
            FirstRunSetup._copy_default_config(config_dir)

            # Initialize database
            FirstRunSetup._initialize_database(config_dir)

            # Note: Model download is now handled through the
            # recommendation dialog after UI initialization

            logger.info("First-run setup completed successfully")

        except Exception as e:
            logger.error(f"Error during first-run setup: {e}")
            raise

    @staticmethod
    def show_model_recommendation_dialog(
        model_manager,
        i18n,
        parent=None
    ) -> bool:
        """
        Show model recommendation dialog on first run.

        Args:
            model_manager: ModelManager instance
            i18n: I18nQtManager instance for translations
            parent: Parent widget for the dialog

        Returns:
            True if user chose to download, False otherwise
        """
        try:
            # Check if any models are already downloaded
            downloaded_models = model_manager.get_downloaded_models()
            if downloaded_models:
                logger.info(
                    "Models already downloaded, "
                    "skipping recommendation dialog"
                )
                return False

            # Get recommended model
            recommended_model_name = model_manager.recommend_model()
            recommended_model = model_manager.get_model(
                recommended_model_name
            )

            if not recommended_model:
                logger.warning(
                    f"Could not get info for recommended model: "
                    f"{recommended_model_name}"
                )
                return False

            # Import here to avoid circular dependencies
            from PyQt6.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                QPushButton, QWidget
            )
            from PyQt6.QtCore import Qt

            # Create dialog
            dialog = QDialog(parent)
            dialog.setWindowTitle(
                i18n.t('settings.model_management.first_run_title')
            )
            dialog.setMinimumWidth(500)

            layout = QVBoxLayout(dialog)

            # Title
            title_label = QLabel(
                i18n.t('settings.model_management.first_run_welcome')
            )
            title_label.setWordWrap(True)
            title_font = title_label.font()
            title_font.setPointSize(14)
            title_font.setBold(True)
            title_label.setFont(title_font)
            layout.addWidget(title_label)

            # Spacing
            layout.addSpacing(20)

            # Recommendation message
            recommendation_text = i18n.t(
                'settings.model_management.first_run_recommendation',
                model_name=recommended_model.full_name
            )
            recommendation_label = QLabel(recommendation_text)
            recommendation_label.setWordWrap(True)
            layout.addWidget(recommendation_label)

            # Spacing
            layout.addSpacing(10)

            # Model info card
            info_card = QWidget()
            info_card.setStyleSheet(
                "QWidget { "
                "background-color: #e8f4f8; "
                "border: 1px solid #b3d9e6; "
                "border-radius: 8px; "
                "padding: 15px; "
                "}"
            )
            info_layout = QVBoxLayout(info_card)

            # Model name
            model_name_label = QLabel(
                f"<b>{recommended_model.full_name}</b>"
            )
            model_name_label.setStyleSheet("color: #1a1a1a; font-size: 14px;")
            info_layout.addWidget(model_name_label)

            # Model details
            details_text = (
                f"{i18n.t('settings.model_management.size')}: "
                f"{recommended_model.size_mb} MB<br>"
                f"{i18n.t('settings.model_management.speed')}: "
                f"{i18n.t(f'settings.model_management.speed_{recommended_model.speed}')}<br>"
                f"{i18n.t('settings.model_management.accuracy')}: "
                f"{i18n.t(f'settings.model_management.accuracy_{recommended_model.accuracy}')}"
            )
            details_label = QLabel(details_text)
            details_label.setWordWrap(True)
            details_label.setStyleSheet("color: #333333; font-size: 12px;")
            info_layout.addWidget(details_label)

            layout.addWidget(info_card)

            # Spacing
            layout.addSpacing(20)

            # Reason for recommendation
            system_info = model_manager.get_recommendation_context()
            memory_gb = system_info['memory_gb']
            has_gpu = system_info['has_gpu']

            reason_parts = []
            if memory_gb < 8:
                reason_parts.append(
                    i18n.t('settings.model_management.reason_low_memory')
                )
            elif memory_gb < 16:
                reason_parts.append(
                    i18n.t('settings.model_management.reason_medium_memory')
                )
            else:
                reason_parts.append(
                    i18n.t('settings.model_management.reason_high_memory')
                )

            if has_gpu:
                reason_parts.append(
                    i18n.t('settings.model_management.reason_gpu_available')
                )
            else:
                reason_parts.append(
                    i18n.t('settings.model_management.reason_no_gpu')
                )

            reason_text = " ".join(reason_parts)
            reason_label = QLabel(reason_text)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("color: #b0b0b0; font-size: 12px;")
            layout.addWidget(reason_label)

            # Spacing
            layout.addSpacing(20)

            # Buttons
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            # Later button
            later_button = QPushButton(
                i18n.t('settings.model_management.download_later')
            )
            later_button.clicked.connect(dialog.reject)
            button_layout.addWidget(later_button)

            # Download button
            download_button = QPushButton(
                i18n.t('settings.model_management.download_now')
            )
            download_button.setDefault(True)
            download_button.setStyleSheet(
                "QPushButton { "
                "background-color: #0078d4; "
                "color: white; "
                "padding: 8px 16px; "
                "border-radius: 4px; "
                "} "
                "QPushButton:hover { "
                "background-color: #106ebe; "
                "}"
            )
            download_button.clicked.connect(dialog.accept)
            button_layout.addWidget(download_button)

            layout.addLayout(button_layout)

            # Show dialog
            result = dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                logger.info(
                    f"User chose to download recommended model: "
                    f"{recommended_model_name}"
                )
                # Start download in a separate thread with its own event loop
                from PyQt6.QtCore import QThreadPool, QRunnable
                
                def run_download():
                    """在新线程中运行下载"""
                    try:
                        # 创建新的事件循环
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # 运行下载
                        loop.run_until_complete(
                            model_manager.download_model(recommended_model_name)
                        )
                        
                        loop.close()
                        logger.info(f"Model {recommended_model_name} download completed")
                    except Exception as e:
                        logger.error(f"Download failed in thread: {e}")
                
                class DownloadRunnable(QRunnable):
                    def run(self):
                        run_download()
                
                QThreadPool.globalInstance().start(DownloadRunnable())
                return True
            else:
                logger.info("User chose to download model later")
                return False

        except Exception as e:
            logger.error(
                f"Error showing model recommendation dialog: {e}"
            )
            return False

    @staticmethod
    def _copy_default_config(config_dir: Path) -> None:
        """
        Copy default configuration file to user directory.

        Args:
            config_dir: User configuration directory
        """
        try:
            # Get the default config file path
            default_config = (
                Path(__file__).parent.parent / "config" /
                "default_config.json"
            )
            user_config = config_dir / "app_config.json"

            if not user_config.exists():
                shutil.copy(default_config, user_config)
                logger.info(
                    f"Copied default configuration to {user_config}"
                )
            else:
                logger.info("User configuration already exists, skipping")

        except Exception as e:
            logger.error(f"Error copying default configuration: {e}")
            raise

    @staticmethod
    def _initialize_database(config_dir: Path, security_manager: Optional["SecurityManager"] = None) -> None:
        """
        Initialize the database schema.

        Args:
            config_dir: User configuration directory
            security_manager: Optional pre-configured SecurityManager instance
        """
        try:
            # Import here to avoid circular dependencies
            from data.database.connection import DatabaseConnection
            from data.security.encryption import SecurityManager

            if security_manager is None:
                security_manager = SecurityManager(str(config_dir))

            db_path = config_dir / "data.db"
            logger.info(f"Initializing database at {db_path}")

            db_encryption_key = security_manager.encryption_key[:32].hex()
            db = DatabaseConnection(str(db_path), encryption_key=db_encryption_key)
            db.initialize_schema()

            encryption_active = db.is_encryption_enabled()
            if not encryption_active:
                logger.warning("Database encryption is not active after initialization; attempting PRAGMA rekey.")
                rekey_success = db.rekey(db_encryption_key)
                if rekey_success:
                    encryption_active = True
                    logger.info("Database encryption activated via PRAGMA rekey during initialization.")
                else:
                    logger.warning("SQLCipher not available; database remains unencrypted after initialization.")

            if encryption_active:
                logger.info("Database initialized successfully with SQLCipher encryption")
            else:
                logger.info("Database initialized without SQLCipher encryption")

        except ImportError:
            logger.warning(
                "Database connection module not yet implemented, "
                "skipping database initialization"
            )
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise




class FirstRunWizard:
    """
    Welcome wizard for first-time users.
    
    Guides users through initial setup including language selection,
    theme selection, and model download.
    """
    
    @staticmethod
    def show_wizard(config_manager, model_manager, i18n, parent=None):
        """
        Show the first run wizard.
        
        Args:
            config_manager: ConfigManager instance
            model_manager: ModelManager instance
            i18n: I18nQtManager instance
            parent: Parent widget
            
        Returns:
            True if wizard was completed, False if cancelled
        """
        try:
            from PyQt6.QtWidgets import (
                QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
                QLabel, QComboBox, QRadioButton, QButtonGroup,
                QPushButton, QProgressBar, QWidget, QFileDialog
            )
            from PyQt6.QtCore import Qt, QThread, pyqtSignal
            from PyQt6.QtGui import QFont
            
            class WelcomePage(QWizardPage):
                """Welcome page with introduction."""
                
                def __init__(self, i18n):
                    super().__init__()
                    self.i18n = i18n
                    self.setTitle(i18n.t('wizard.welcome.title'))
                    
                    layout = QVBoxLayout()
                    
                    # Welcome message
                    welcome_label = QLabel(
                        i18n.t('wizard.welcome.message')
                    )
                    welcome_label.setWordWrap(True)
                    font = welcome_label.font()
                    font.setPointSize(12)
                    welcome_label.setFont(font)
                    layout.addWidget(welcome_label)
                    
                    layout.addSpacing(20)
                    
                    # Features list
                    features_label = QLabel(
                        i18n.t('wizard.welcome.features')
                    )
                    features_label.setWordWrap(True)
                    layout.addWidget(features_label)
                    
                    layout.addStretch()
                    
                    self.setLayout(layout)
            
            class LanguagePage(QWizardPage):
                """Language selection page."""
                
                def __init__(self, i18n, config_manager):
                    super().__init__()
                    self.i18n = i18n
                    self.config_manager = config_manager
                    self.setTitle(i18n.t('wizard.language.title'))
                    self.setSubTitle(i18n.t('wizard.language.subtitle'))
                    
                    layout = QVBoxLayout()
                    
                    # Language selection
                    lang_label = QLabel(i18n.t('wizard.language.select'))
                    layout.addWidget(lang_label)
                    
                    self.language_combo = QComboBox()
                    self.language_combo.addItem("中文（简体）", "zh_CN")
                    self.language_combo.addItem("English", "en_US")
                    self.language_combo.addItem("Français", "fr_FR")
                    
                    # Set current language
                    current_lang = config_manager.get('ui.language', 'zh_CN')
                    index = self.language_combo.findData(current_lang)
                    if index >= 0:
                        self.language_combo.setCurrentIndex(index)
                    
                    layout.addWidget(self.language_combo)
                    
                    layout.addSpacing(20)
                    
                    # Info message
                    info_label = QLabel(i18n.t('wizard.language.info'))
                    info_label.setWordWrap(True)
                    info_label.setStyleSheet("color: #666;")
                    layout.addWidget(info_label)
                    
                    layout.addStretch()
                    
                    self.setLayout(layout)
                    
                    # Register field for wizard
                    self.registerField("language", self.language_combo)
                
                def get_selected_language(self):
                    """Get the selected language code."""
                    return self.language_combo.currentData()
            
            class ThemePage(QWizardPage):
                """Theme selection page."""
                
                def __init__(self, i18n, config_manager):
                    super().__init__()
                    self.i18n = i18n
                    self.config_manager = config_manager
                    self.setTitle(i18n.t('wizard.theme.title'))
                    self.setSubTitle(i18n.t('wizard.theme.subtitle'))
                    
                    layout = QVBoxLayout()
                    
                    # Theme selection
                    theme_label = QLabel(i18n.t('wizard.theme.select'))
                    layout.addWidget(theme_label)
                    
                    layout.addSpacing(10)
                    
                    # Radio buttons for themes
                    self.theme_group = QButtonGroup()
                    
                    self.light_radio = QRadioButton(
                        i18n.t('settings.theme.light')
                    )
                    self.dark_radio = QRadioButton(
                        i18n.t('settings.theme.dark')
                    )
                    self.system_radio = QRadioButton(
                        i18n.t('settings.theme.system')
                    )
                    
                    self.theme_group.addButton(self.light_radio, 0)
                    self.theme_group.addButton(self.dark_radio, 1)
                    self.theme_group.addButton(self.system_radio, 2)
                    
                    # Set current theme
                    current_theme = config_manager.get('ui.theme', 'light')
                    if current_theme == 'light':
                        self.light_radio.setChecked(True)
                    elif current_theme == 'dark':
                        self.dark_radio.setChecked(True)
                    else:
                        self.system_radio.setChecked(True)
                    
                    layout.addWidget(self.light_radio)
                    layout.addWidget(self.dark_radio)
                    layout.addWidget(self.system_radio)
                    
                    layout.addSpacing(20)
                    
                    # Info message
                    info_label = QLabel(i18n.t('wizard.theme.info'))
                    info_label.setWordWrap(True)
                    info_label.setStyleSheet("color: #666;")
                    layout.addWidget(info_label)
                    
                    layout.addStretch()
                    
                    self.setLayout(layout)
                
                def get_selected_theme(self):
                    """Get the selected theme."""
                    if self.light_radio.isChecked():
                        return 'light'
                    elif self.dark_radio.isChecked():
                        return 'dark'
                    else:
                        return 'system'
            
            class ModelDownloadPage(QWizardPage):
                """Model download page."""
                
                def __init__(self, i18n, model_manager):
                    super().__init__()
                    self.i18n = i18n
                    self.model_manager = model_manager
                    self.download_started = False
                    self.download_completed = False
                    
                    self.setTitle(i18n.t('wizard.model.title'))
                    self.setSubTitle(i18n.t('wizard.model.subtitle'))
                    
                    layout = QVBoxLayout()
                    
                    # Recommendation
                    recommended_model = model_manager.recommend_model()
                    recommended_info = model_manager.get_model(
                        recommended_model
                    )
                    
                    rec_label = QLabel(
                        i18n.t(
                            'wizard.model.recommendation',
                            model=recommended_info.full_name if recommended_info else recommended_model
                        )
                    )
                    rec_label.setWordWrap(True)
                    layout.addWidget(rec_label)
                    
                    layout.addSpacing(10)
                    
                    # Model info
                    if recommended_info:
                        info_text = (
                            f"{i18n.t('settings.model_management.size')}: "
                            f"{recommended_info.size_mb} MB\n"
                            f"{i18n.t('settings.model_management.speed')}: "
                            f"{i18n.t(f'settings.model_management.speed_{recommended_info.speed}')}\n"
                            f"{i18n.t('settings.model_management.accuracy')}: "
                            f"{i18n.t(f'settings.model_management.accuracy_{recommended_info.accuracy}')}"
                        )
                        info_label = QLabel(info_text)
                        info_label.setStyleSheet(
                            "background-color: #f0f0f0; "
                            "padding: 10px; "
                            "border-radius: 5px;"
                        )
                        layout.addWidget(info_label)
                    
                    layout.addSpacing(20)
                    
                    # Download button
                    self.download_button = QPushButton(
                        i18n.t('wizard.model.download_now')
                    )
                    self.download_button.clicked.connect(
                        self._start_download
                    )
                    layout.addWidget(self.download_button)
                    
                    # Progress bar
                    self.progress_bar = QProgressBar()
                    self.progress_bar.setVisible(False)
                    layout.addWidget(self.progress_bar)
                    
                    # Status label
                    self.status_label = QLabel("")
                    self.status_label.setWordWrap(True)
                    layout.addWidget(self.status_label)
                    
                    layout.addSpacing(10)
                    
                    # Skip info
                    skip_label = QLabel(i18n.t('wizard.model.skip_info'))
                    skip_label.setWordWrap(True)
                    skip_label.setStyleSheet("color: #666; font-size: 10pt;")
                    layout.addWidget(skip_label)
                    
                    layout.addStretch()
                    
                    self.setLayout(layout)
                    
                    self.recommended_model = recommended_model
                
                def _start_download(self):
                    """Start model download."""
                    if self.download_started:
                        return
                    
                    self.download_started = True
                    self.download_button.setEnabled(False)
                    self.progress_bar.setVisible(True)
                    self.progress_bar.setRange(0, 0)  # Indeterminate
                    self.status_label.setText(
                        self.i18n.t('wizard.model.downloading')
                    )
                    
                    # Start download in thread
                    from PyQt6.QtCore import QThreadPool, QRunnable
                    
                    def run_download():
                        """Run download in thread."""
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        try:
                            loop.run_until_complete(
                                self.model_manager.download_model(
                                    self.recommended_model
                                )
                            )
                            self.download_completed = True

                            # Update UI in main thread
                            from PyQt6.QtCore import QMetaObject, Qt
                            QMetaObject.invokeMethod(
                                self,
                                "_on_download_complete",
                                Qt.ConnectionType.QueuedConnection
                            )
                        except Exception as e:
                            logger.error(f"Download failed: {e}")
                            # Update UI in main thread
                            from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
                            QMetaObject.invokeMethod(
                                self,
                                "_on_download_error",
                                Qt.ConnectionType.QueuedConnection,
                                Q_ARG(str, str(e))
                            )
                        finally:
                            loop.close()

                    class DownloadRunnable(QRunnable):
                        def __init__(self, func):
                            super().__init__()
                            self.func = func
                        
                        def run(self):
                            self.func()
                    
                    QThreadPool.globalInstance().start(
                        DownloadRunnable(run_download)
                    )
                
                def _on_download_complete(self):
                    """Handle download completion."""
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(100)
                    self.status_label.setText(
                        self.i18n.t('wizard.model.download_complete')
                    )
                    self.status_label.setStyleSheet("color: green;")
                    
                    # Enable next button
                    wizard = self.wizard()
                    if wizard:
                        wizard.button(QWizard.WizardButton.NextButton).setEnabled(True)
                
                def _on_download_error(self, error_msg):
                    """Handle download error."""
                    self.progress_bar.setVisible(False)
                    self.status_label.setText(
                        self.i18n.t('wizard.model.download_error', error=error_msg)
                    )
                    self.status_label.setStyleSheet("color: red;")
                    self.download_button.setEnabled(True)
                    self.download_started = False
            
            class CompletePage(QWizardPage):
                """Completion page."""
                
                def __init__(self, i18n):
                    super().__init__()
                    self.i18n = i18n
                    self.setTitle(i18n.t('wizard.complete.title'))
                    
                    layout = QVBoxLayout()
                    
                    # Completion message
                    complete_label = QLabel(
                        i18n.t('wizard.complete.message')
                    )
                    complete_label.setWordWrap(True)
                    font = complete_label.font()
                    font.setPointSize(12)
                    complete_label.setFont(font)
                    layout.addWidget(complete_label)
                    
                    layout.addSpacing(20)
                    
                    # Next steps
                    next_steps_label = QLabel(
                        i18n.t('wizard.complete.next_steps')
                    )
                    next_steps_label.setWordWrap(True)
                    layout.addWidget(next_steps_label)
                    
                    layout.addStretch()
                    
                    self.setLayout(layout)
            
            # Create wizard
            wizard = QWizard(parent)
            wizard.setWindowTitle(i18n.t('wizard.title'))
            wizard.setWizardStyle(QWizard.WizardStyle.ModernStyle)
            wizard.setMinimumSize(600, 450)
            
            # Add pages
            welcome_page = WelcomePage(i18n)
            language_page = LanguagePage(i18n, config_manager)
            theme_page = ThemePage(i18n, config_manager)
            model_page = ModelDownloadPage(i18n, model_manager)
            complete_page = CompletePage(i18n)
            
            wizard.addPage(welcome_page)
            wizard.addPage(language_page)
            wizard.addPage(theme_page)
            wizard.addPage(model_page)
            wizard.addPage(complete_page)
            
            # Show wizard
            result = wizard.exec()
            
            if result == QWizard.DialogCode.Accepted:
                # Save settings
                selected_language = language_page.get_selected_language()
                selected_theme = theme_page.get_selected_theme()
                
                config_manager.set('ui.language', selected_language)
                config_manager.set('ui.theme', selected_theme)
                config_manager.save()
                
                # Apply language change
                i18n.set_language(selected_language)
                
                logger.info(
                    f"First run wizard completed: "
                    f"language={selected_language}, theme={selected_theme}"
                )
                return True
            else:
                logger.info("First run wizard cancelled")
                return False
                
        except Exception as e:
            logger.error(f"Error showing first run wizard: {e}")
            return False
