# SPDX-License-Identifier: Apache-2.0
"""Centralized SVG icons generation."""

from __future__ import annotations

from core.qt_imports import QIcon, QPixmap

_SVG_TEMPLATES = {
    # System & Document Icons
    "create_text": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2.5 14.5C2.5 15.0523 2.94772 15.5 3.5 15.5H12.5C13.0523 15.5 13.5 15.0523 13.5 14.5V1.5C13.5 0.947715 13.0523 0.5 12.5 0.5H3.5C2.94772 0.5 2.5 0.947715 2.5 1.5V14.5Z" stroke="{color}" stroke-linejoin="round"/>
            <path d="M5.5 4.5H10.5M5.5 8H10.5M5.5 11.5H8.5" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,
    "create_folder": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M1.5 3C1.5 2.44772 1.94772 2 2.5 2H6.5L8 4H13.5C14.0523 4 14.5 4.44772 14.5 5V13C14.5 13.5523 14.0523 14 13.5 14H2.5C1.94772 14 1.5 13.5523 1.5 13V3Z" stroke="{color}" stroke-linejoin="round"/>
            <path d="M5 8.5H11M8 5.5V11.5" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,
    "import_media": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 11V2M8 2L4 6M8 2L12 6" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M2 14H14" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,
    "settings": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 10C9.10457 10 10 9.10457 10 8C10 6.89543 9.10457 6 8 6C6.89543 6 6 6.89543 6 8C6 9.10457 6.89543 10 8 10Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 6L11.8 5.6C11.6 5 11.3 4.4 10.9 4L12 2L10.6 0.6L8.5 1.7C8.1 1.4 7.6 1.2 7 1.1L6.6 0H4.6L4.2 2.2C3.6 2.4 3.1 2.7 2.7 3.1L0.6 2L-0.8 3.4L0.3 5.5C0 6.1 -0.2 6.6 -0.3 7.2L-2.5 7.6V9.6L -0.3 10C-0.1 10.6 0.2 11.2 0.6 11.6L-0.5 13.7L0.9 15.1L3 14C3.4 14.3 3.9 14.6 4.5 14.7L4.9 16.9H6.9L7.3 14.7C7.9 14.5 8.4 14.2 8.8 13.8L10.9 14.9L12.3 13.5L11.2 11.4C11.5 10.8 11.8 10.2 11.9 9.6L14.1 9.2V7.2H14V6Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "device_speaker": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 3L4.5 6H2V10H4.5L8 13V3Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M11 5C12.3333 6.66667 12.3333 9.33333 11 11" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M13.5 3C15.5 5.5 15.5 10.5 13.5 13" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "device_mic": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 1V7C8 8.10457 7.10457 9 6 9C4.89543 9 4 8.10457 4 7V1" stroke="{color}" stroke-linecap="round"/>
            <path d="M11 7C11 9.76142 8.76142 12 6 12C3.23858 12 1 9.76142 1 7" stroke="{color}" stroke-linecap="round"/>
            <path d="M6 12V15M4 15H8" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,

    # Navigation Nodes & Document Outline
    "node_inbox": """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1.5 3C1.5 2.17157 2.17157 1.5 3 1.5H11C11.8284 1.5 12.5 2.17157 12.5 3V11C12.5 11.8284 11.8284 12.5 11 12.5H3C2.17157 12.5 1.5 11.8284 1.5 11V3Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M1.5 5.5H5L6 7.5H8L9 5.5H12.5" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "node_folder": """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1.5 3C1.5 2.44772 1.94772 2 2.5 2H5.5L6.5 3.5H11.5C12.0523 3.5 12.5 3.94772 12.5 4.5V11C12.5 11.5523 12.0523 12 11.5 12H2.5C1.94772 12 1.5 11.5523 1.5 11V3Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "node_system_folder": """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1.5 3C1.5 2.44772 1.94772 2 2.5 2H5.5L6.5 3.5H11.5C12.0523 3.5 12.5 3.94772 12.5 4.5V11C12.5 11.5523 12.0523 12 11.5 12H2.5C1.94772 12 1.5 11.5523 1.5 11V3Z" stroke="{color}" stroke-linejoin="round"/>
            <circle cx="7" cy="7.5" r="1.5" fill="{color}"/>
            <path d="M7 4.5V6" stroke="{color}" stroke-linecap="round"/>
            <path d="M7 9V10.5" stroke="{color}" stroke-linecap="round"/>
            <path d="M4 7.5H5.5" stroke="{color}" stroke-linecap="round"/>
            <path d="M8.5 7.5H10" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,
    "node_text": """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 1.5H8.5L11.5 4.5V11.5C11.5 12.0523 11.0523 12.5 10.5 12.5H3C2.44772 12.5 2 12.0523 2 11.5V2.5C2 1.94772 2.44772 1.5 3 1.5Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4.5 6.5H9.5M4.5 9H7.5" stroke="{color}" stroke-linecap="round"/>
        </svg>
    """,
    "node_record": """
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 12.5C10.0376 12.5 12.5 10.0376 12.5 7C12.5 3.96243 10.0376 1.5 7 1.5C3.96243 1.5 1.5 3.96243 1.5 7C1.5 10.0376 3.96243 12.5 7 12.5Z" stroke="{color}" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="7" cy="7" r="2" fill="{color}"/>
        </svg>
    """,
    "import": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M5 2.75H9.25L12 5.5V12.25C12 12.6642 11.6642 13 11.25 13H5C4.58579 13 4.25 12.6642 4.25 12.25V3.5C4.25 3.08579 4.58579 2.75 5 2.75Z" stroke="{color}" stroke-width="1.3" stroke-linejoin="round"/>
          <path d="M9 2.75V5.5H11.75" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M8 7V10.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M6.5 9L8 10.5L9.5 9" stroke="{color}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "new_note": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M3.75 12.25L4.3 10.2L10.35 4.15C10.6429 3.85711 11.1178 3.85711 11.4107 4.15L11.85 4.58934C12.1429 4.88223 12.1429 5.35711 11.85 5.65L5.8 11.7L3.75 12.25Z" stroke="{color}" stroke-width="1.3" stroke-linejoin="round"/>
          <path d="M9.75 4.75L11.25 6.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M8 2.75V5.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M6.75 4H9.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
    """,
    "new_folder": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M2.75 4.75C2.75 4.33579 3.08579 4 3.5 4H6.1L7.2 5.1H12.5C12.9142 5.1 13.25 5.43579 13.25 5.85V11.75C13.25 12.1642 12.9142 12.5 12.5 12.5H3.5C3.08579 12.5 2.75 12.1642 2.75 11.75V4.75Z" stroke="{color}" stroke-width="1.3" stroke-linejoin="round"/>
          <path d="M8 7.25V10.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M6.5 8.75H9.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
    """,
    "rename": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M3.75 12.25L4.3 10.2L10.35 4.15C10.6429 3.85711 11.1178 3.85711 11.4107 4.15L11.85 4.58934C12.1429 4.88223 12.1429 5.35711 11.85 5.65L5.8 11.7L3.75 12.25Z" stroke="{color}" stroke-width="1.3" stroke-linejoin="round"/>
          <path d="M9.75 4.75L11.25 6.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
    """,
    "delete": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M4.5 5.25V11.25C4.5 11.6642 4.83579 12 5.25 12H10.75C11.1642 12 11.5 11.6642 11.5 11.25V5.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M3.5 4H12.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M6.25 4V3.25C6.25 2.83579 6.58579 2.5 7 2.5H9C9.41421 2.5 9.75 2.83579 9.75 3.25V4" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M6.75 6.5V10.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
          <path d="M9.25 6.5V10.25" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
        </svg>
    """,

    # Recording Control (Realtime Base)
    "record_start": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="{color}" stroke-width="2"/>
        </svg>
    """,
    "record_stop": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="4" y="4" width="8" height="8" fill="{color}"/>
        </svg>
    """,
    "record_pause": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="5" y="4" width="2" height="8" fill="{color}"/>
            <rect x="9" y="4" width="2" height="8" fill="{color}"/>
        </svg>
    """,
    "minimize": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M12 10H8V14" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 10L15 13" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4 6H8V2" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4 6L1 3" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,

    # Recording Dock Base Missing SVGs
    "settings": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6.4 1.5h3.2l.52 1.67c.28.09.55.2.82.34l1.62-.72 2.26 2.26-.72 1.62c.14.27.25.54.34.82l1.67.52v3.2l-1.67.52c-.09.28-.2.55-.34.82l.72 1.62-2.26 2.26-1.62-.72a5.2 5.2 0 0 1-.82.34L9.6 14.5H6.4l-.52-1.67a5.2 5.2 0 0 1-.82-.34l-1.62.72-2.26-2.26.72-1.62a5.2 5.2 0 0 1-.34-.82L.5 9.9V6.7l1.67-.52c.09-.28.2-.55.34-.82l-.72-1.62 2.26-2.26 1.62.72c.27-.14.54-.25.82-.34L6.4 1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <circle cx="8" cy="8.3" r="2.1" stroke="{color}" stroke-width="1.2"/>
        </svg>
    """,
    "overlay": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="2" y="3" width="12" height="8.5" rx="2" stroke="{color}" stroke-width="1.2"/>
            <path d="M5 13h6" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <circle cx="11.5" cy="7.25" r="1.2" fill="{color}"/>
        </svg>
    """,
    "document": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 1.8h5.2L12.5 5v8.7c0 .83-.67 1.5-1.5 1.5H4c-.83 0-1.5-.67-1.5-1.5V3.3c0-.83.67-1.5 1.5-1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M9.2 1.8V5h3.3" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M5.4 8h5.2M5.4 10.6h5.2" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    """,
    "spark": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 1.5l1.37 3.43L12.8 6.3l-3.43 1.37L8 11.1 6.63 7.67 3.2 6.3l3.43-1.37L8 1.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M12.2 10.2l.63 1.58 1.57.63-1.57.62-.63 1.58-.62-1.58-1.58-.62 1.58-.63.62-1.58Z" fill="{color}"/>
        </svg>
    """,
    "transcript": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3.5h10v6.8a1 1 0 0 1-1 1H7.4l-2.9 2V11.3H4a1 1 0 0 1-1-1V3.5Z" stroke="{color}" stroke-width="1.2" stroke-linejoin="round"/>
            <path d="M5.2 6h5.6M5.2 8.2h4.1" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
    """,
    "translation": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2.5 4.5h7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M7.5 2.5L9.5 4.5L7.5 6.5" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M13.5 11.5h-7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M8.5 9.5L6.5 11.5L8.5 13.5" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    """,
    "auto-secondary": """
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2.2a5.8 5.8 0 1 1-4.1 1.7" stroke="{color}" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M2.3 2.6h3v3" stroke="{color}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M8 5.1l.88 2.22 2.22.88-2.22.89L8 11.32l-.88-2.22-2.22-.89 2.22-.88L8 5.1Z" fill="{color}"/>
        </svg>
    """,

    # Audio Player (Playback Context)
    "play": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M8 5v14l11-7z" fill="{color}"/>
        </svg>
    """,
    "pause": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="{color}"/>
        </svg>
    """,
    "stop": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <rect x="6" y="6" width="12" height="12" fill="{color}"/>
        </svg>
    """,
    "rewind": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M11 18V6l-8.5 6 8.5 6zm.5-6l8.5 6V6l-8.5 6z" fill="{color}"/>
        </svg>
    """,
    "fast_forward": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z" fill="{color}"/>
        </svg>
    """,
    "volume_up": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="{color}"/>
        </svg>
    """,
    "volume_mute": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" fill="{color}"/>
        </svg>
    """,
    "subtitles": """
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-6 10H8v-2h6v2zm4-4H6V8h12v2z" fill="{color}"/>
        </svg>
    """
}

def build_svg_icon(icon_name: str, color: str) -> QIcon:
    """
    Generate a recolored QIcon from a central SVG template.
    
    Args:
        icon_name: The name of the SVG template defined in _SVG_TEMPLATES.
        color: The hex/rgb string representation for recoloring.
    """
    if icon_name not in _SVG_TEMPLATES:
        return QIcon()

    svg_markup = _SVG_TEMPLATES[icon_name].format(color=color)
    pixmap = QPixmap()
    if not pixmap.loadFromData(svg_markup.encode("utf-8"), "SVG"):
        return QIcon()

    return QIcon(pixmap)
