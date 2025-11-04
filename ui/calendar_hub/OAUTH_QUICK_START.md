# OAuth Quick Start Guide

## For Users

### Connecting Your Calendar

1. **Open EchoNote** and navigate to the Calendar Hub

2. **Click "Add Account"** button

3. **Select your calendar provider**:

   - Google Calendar
   - Outlook Calendar

4. **Authorize in browser**:

   - Your default browser will open
   - Sign in to your account if needed
   - Review the permissions EchoNote is requesting
   - Click "Allow" or "Accept"

5. **Return to EchoNote**:

   - The browser will show a success message
   - You can close the browser tab
   - EchoNote will show your connected account

6. **Your calendar is now synced!**
   - Events will appear in the calendar view
   - Automatic sync runs every 15 minutes

### Disconnecting Your Calendar

1. Find your account badge in the Calendar Hub
2. Click the **×** button on the badge
3. Confirm the disconnection
4. All synced events will be removed

## For Developers

### Setting Up OAuth Credentials

#### Google Calendar

1. **Create a Google Cloud Project**:

   - Go to https://console.cloud.google.com/
   - Create a new project or select existing

2. **Enable Google Calendar API**:

   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

3. **Create OAuth Credentials**:

   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as application type
   - Name it "EchoNote"

4. **Configure Redirect URI**:

   - Add `http://localhost:8080/callback` to authorized redirect URIs

5. **Copy Credentials**:
   - Copy the Client ID and Client Secret
   - Add to `config/default_config.json`:
   ```json
   {
     "calendar": {
       "oauth": {
         "google": {
           "client_id": "YOUR_CLIENT_ID_HERE",
           "client_secret": "YOUR_CLIENT_SECRET_HERE"
         }
       }
     }
   }
   ```

#### Outlook Calendar

1. **Register Azure AD Application**:

   - Go to https://portal.azure.com/
   - Navigate to "Azure Active Directory" > "App registrations"
   - Click "New registration"
   - Name it "EchoNote"

2. **Configure Redirect URI**:

   - Add `http://localhost:8080/callback` as a redirect URI
   - Select "Public client/native" platform

3. **Grant Permissions**:

   - Go to "API permissions"
   - Add "Microsoft Graph" permissions:
     - Calendars.Read
     - Calendars.ReadWrite
     - User.Read
   - Grant admin consent if required

4. **Create Client Secret**:

   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Copy the secret value (you won't see it again!)

5. **Copy Credentials**:
   - Copy the Application (client) ID and secret
   - Add to `config/default_config.json`:
   ```json
   {
     "calendar": {
       "oauth": {
         "outlook": {
           "client_id": "YOUR_CLIENT_ID_HERE",
           "client_secret": "YOUR_CLIENT_SECRET_HERE"
         }
       }
     }
   }
   ```

### Testing

Run the test script to verify OAuth flow:

```bash
python test_oauth_dialog.py
```

This will open a test window where you can test the OAuth flow without running the full application.

### Troubleshooting

**Port 8080 is already in use**:

- Change the port in config:
  ```json
  {
    "calendar": {
      "oauth": {
        "callback_port": 8081,
        "redirect_uri": "http://localhost:8081/callback"
      }
    }
  }
  ```
- Update the redirect URI in your OAuth app settings

**Browser doesn't open**:

- Ensure you have a default browser configured
- Try manually opening the authorization URL

**Authorization fails**:

- Check that credentials are correctly configured
- Verify redirect URI matches in both config and OAuth app
- Check that required API scopes are enabled
- Review application logs for detailed errors

**Token storage errors**:

- Ensure `~/.echonote/` directory is writable
- Check file permissions on `oauth_tokens.enc`

## Security Notes

- **Never commit OAuth credentials** to version control
- **Keep client secrets secure** - treat them like passwords
- **Tokens are encrypted** before storage using AES-256
- **Token file permissions** are set to 0600 (owner only)
- **No passwords stored** - only OAuth tokens
- **HTTPS only** - all API communication is encrypted

## Support

For issues or questions:

1. Check the logs in `~/.echonote/logs/`
2. Review the full documentation in `OAUTH_IMPLEMENTATION.md`
3. Open an issue on GitHub with log excerpts (remove sensitive data)

## References

- [Google Calendar API](https://developers.google.com/calendar/api)
- [Microsoft Graph Calendar](https://docs.microsoft.com/en-us/graph/api/resources/calendar)
- [OAuth 2.0 Specification](https://oauth.net/2/)
