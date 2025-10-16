"""
Splash screen for application startup.

Displays a splash screen with progress updates during initialization.
"""

import logging
from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont


logger = logging.getLogger(__name__)


class SplashScreen(QSplashScreen):
    """
    Splash screen displayed during application startup.
    
    Shows application name, version, and initialization progress.
    """
    
    def __init__(self, width: int = 500, height: int = 300):
        """
        Initialize splash screen.
        
        Args:
            width: Splash screen width
            height: Splash screen height
        """
        # Create a simple pixmap for the splash screen
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(33, 150, 243))  # Material Blue
        
        super().__init__(pixmap)
        
        self.width = width
        self.height = height
        
        # Set window flags
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        # Initialize progress text
        self._progress_text = "Initializing..."
        self._progress_percent = 0
        
        logger.debug("Splash screen initialized")
    
    def drawContents(self, painter: QPainter):
        """
        Draw splash screen contents.
        
        Args:
            painter: QPainter instance
        """
        painter.setPen(QColor(255, 255, 255))
        
        # Draw application name
        title_font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            20, 80,
            "EchoNote"
        )
        
        # Draw version
        version_font = QFont("Arial", 12)
        painter.setFont(version_font)
        painter.drawText(
            20, 110,
            "v1.0.0"
        )
        
        # Draw progress text
        progress_font = QFont("Arial", 11)
        painter.setFont(progress_font)
        painter.drawText(
            20, self.height - 60,
            self._progress_text
        )
        
        # Draw progress bar
        # Reserve space for percentage text (60px)
        bar_width = self.width - 100
        bar_height = 20
        bar_x = 20
        bar_y = self.height - 40
        
        # Background
        painter.fillRect(
            bar_x, bar_y, bar_width, bar_height,
            QColor(255, 255, 255, 50)
        )
        
        # Progress
        progress_width = int(bar_width * (self._progress_percent / 100))
        painter.fillRect(
            bar_x, bar_y, progress_width, bar_height,
            QColor(255, 255, 255)
        )
        
        # Progress percentage (right-aligned)
        percent_text = f"{self._progress_percent}%"
        percent_font = QFont("Arial", 11, QFont.Weight.Bold)
        painter.setFont(percent_font)
        
        # Calculate text width for right alignment
        from PyQt6.QtGui import QFontMetrics
        metrics = QFontMetrics(percent_font)
        text_width = metrics.horizontalAdvance(percent_text)
        
        # Draw percentage at the right edge
        painter.drawText(
            self.width - text_width - 20, bar_y + 15,
            percent_text
        )
    
    def show_progress(self, message: str, percent: int = None):
        """
        Update progress message and percentage.
        
        Args:
            message: Progress message
            percent: Progress percentage (0-100), optional
        """
        self._progress_text = message
        if percent is not None:
            self._progress_percent = max(0, min(100, percent))
        
        # Force repaint
        self.repaint()
        
        # Process events to keep UI responsive
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        logger.debug(f"Splash progress: {message} ({self._progress_percent}%)")
    
    def finish_with_delay(self, main_window, delay_ms: int = 500):
        """
        Finish splash screen with a delay.
        
        Args:
            main_window: Main window to show after splash
            delay_ms: Delay in milliseconds before closing splash
        """
        def close_splash():
            self.finish(main_window)
            logger.info("Splash screen closed")
        
        QTimer.singleShot(delay_ms, close_splash)
