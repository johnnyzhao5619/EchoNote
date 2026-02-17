#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Helper script to securely set up OAuth secrets for EchoNote.
Prompts user for client IDs and secrets and stores them in the encrypted SecretsManager.
"""

import sys
import getpass
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.security.secrets_manager import SecretsManager
from utils.logger import setup_logging

def main():
    setup_logging()
    logger = logging.getLogger("echonote.scripts.setup_oauth")
    
    print("=" * 60)
    print("EchoNote OAuth Secrets Setup")
    print("=" * 60)
    print("This script will help you securely store your OAuth credentials.")
    print("Credentials are encrypted and stored in ~/.echonote/secrets.enc\n")
    
    try:
        secrets_manager = SecretsManager()
        
        # Google Calendar
        print("\n--- Google Calendar ---")
        use_google = input("Configure Google Calendar? (y/N): ").lower().strip() == 'y'
        
        if use_google:
            client_id = input("Google Client ID: ").strip()
            client_secret = getpass.getpass("Google Client Secret: ").strip()
            
            if client_id and client_secret:
                secrets_manager.set_secret("calendar_google_client_id", client_id)
                secrets_manager.set_secret("calendar_google_client_secret", client_secret)
                print("✓ Google Calendar credentials saved.")
            else:
                print("! Skipped Google Calendar (empty input).")
        
        # Outlook Calendar
        print("\n--- Outlook Calendar ---")
        use_outlook = input("Configure Outlook Calendar? (y/N): ").lower().strip() == 'y'
        
        if use_outlook:
            client_id = input("Outlook Client ID: ").strip()
            client_secret = getpass.getpass("Outlook Client Secret: ").strip()
            
            if client_id and client_secret:
                secrets_manager.set_secret("calendar_outlook_client_id", client_id)
                secrets_manager.set_secret("calendar_outlook_client_secret", client_secret)
                print("✓ Outlook Calendar credentials saved.")
            else:
                print("! Skipped Outlook Calendar (empty input).")
                
        print("\n" + "=" * 60)
        print("Setup complete!")
        print("Restart EchoNote for changes to take effect.")
        
    except Exception as e:
        logger.error(f"Error saving secrets: {e}")
        print(f"\nERROR: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
