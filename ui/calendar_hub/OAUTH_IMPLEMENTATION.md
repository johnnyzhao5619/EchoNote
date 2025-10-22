# OAuth Implementation for Calendar Hub

## Overview

The OAuth implementation for EchoNote's Calendar Hub provides secure authentication and authorization for external calendar services (Google Calendar and Outlook Calendar).

## Components

### 1. OAuthDialog (`oauth_dialog.py`)

A PyQt6 dialog that handles the OAuth 2.0 authorization flow:

- **Features**:

  - Opens system browser for user authorization
  - Runs local HTTP server on a configurable callback host/port (8080 by default)
  - Displays authorization status and progress
  - Handles authorization success and failure
  - Non-blocking UI using QThread for HTTP server

- **Signals**:

  - `authorization_complete(str, str)`: Emitted with authorization code and PKCE `code_verifier` on success
  - `authorization_failed(str)`: Emitted with error message on failure (including state validation errors)

- **Usage**:

  ```python
  request = adapter.get_authorization_url()

  dialog = OAuthDialog(
      provider='google',
      authorization_url=request['authorization_url'],
      i18n=i18n_manager,
      parent=parent_widget,
      callback_host='localhost',  # optional; inferred from configuration if omitted
      callback_port=8080,         # optional; inferred from configuration if omitted
      state=request['state'],
      code_verifier=request['code_verifier'],
  )

  dialog.authorization_complete.connect(handle_success)
  dialog.authorization_failed.connect(handle_error)

  dialog.exec()
  ```

### 2. CalendarHubWidget Integration

The Calendar Hub widget integrates OAuth functionality:

- **OAuth Flow**:

  1. User clicks "Add Account" button
  2. Selects provider (Google/Outlook)
  3. Adapter generates authorization request with PKCE challenge and state token
  4. OAuthDialog opens with authorization URL and securely caches state/code verifier
  5. User authorizes in browser
  6. Callback received with authorization code and state
  7. OAuthDialog validates state before proceeding
  8. Code exchanged for access/refresh tokens (PKCE code verifier included)
  9. Tokens stored securely using OAuthManager
  10. CalendarSyncStatus record created
  11. Initial calendar sync triggered
  12. Account badge displayed

- **Account Management**:
  - Display connected accounts with provider badges
  - Disconnect button on each badge
  - Disconnect removes tokens, sync status, and synced events

### 3. OAuthManager (`data/security/oauth_manager.py`)

Manages secure storage and retrieval of OAuth tokens:

- **Features**:

  - Encrypted token storage using AES-256
  - Token expiration detection
  - Automatic token refresh support
  - Multiple provider support

- **Storage Location**: `~/.echonote/oauth_tokens.enc`

### 4. Calendar Sync Adapters

Both adapters inherit from the shared `OAuthCalendarAdapter` in `engines/calendar_sync/base.py`. The base class centralizes the PKCE flow, token exchange/refresh, and composes an internal `OAuthHttpClient` wrapper around `RetryableHttpClient` so adapters only specify provider-specific scopes and event mappings. Pass `http_client_config` when instantiating an adapter to tweak `timeout`, `max_retry_after`, or `retryable_status_codes` for long-poll calendar endpoints without re-implementing OAuth plumbing.

#### GoogleCalendarAdapter (`engines/calendar_sync/google_calendar.py`)

- **OAuth Endpoints**:

  - Authorization: `https://accounts.google.com/o/oauth2/v2/auth`
  - Token Exchange: `https://oauth2.googleapis.com/token`
  - Revoke: `https://oauth2.googleapis.com/revoke`

- **Scopes**:
  - `https://www.googleapis.com/auth/calendar.readonly`
  - `https://www.googleapis.com/auth/calendar.events`

#### OutlookCalendarAdapter (`engines/calendar_sync/outlook_calendar.py`)

- **OAuth Endpoints**:

  - Authorization: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize`
  - Token Exchange: `https://login.microsoftonline.com/common/oauth2/v2.0/token`

- **Scopes**:
  - `Calendars.Read`
  - `Calendars.ReadWrite`
  - `User.Read`

## Configuration

OAuth credentials are configured in `config/default_config.json`:

```json
{
  "calendar": {
    "oauth": {
      "redirect_uri": "http://localhost:8080/callback",
      "callback_port": 8080,
      "google": {
        "client_id": "YOUR_GOOGLE_CLIENT_ID",
        "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
      },
      "outlook": {
        "client_id": "YOUR_OUTLOOK_CLIENT_ID",
        "client_secret": "YOUR_OUTLOOK_CLIENT_SECRET"
      }
    }
  }
}
```

If you change `callback_port`, update the `redirect_uri` to use the same port and register the URI with the provider. The `CalendarHubWidget` forwards the configured host/port to `OAuthDialog`, keeping the UI and the local callback listener in sync.

### Obtaining OAuth Credentials

#### Google Calendar

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth 2.0 credentials (Desktop app)
5. Add `http://localhost:8080/callback` as authorized redirect URI
6. Copy client ID and secret to config

#### Outlook Calendar

1. Go to [Azure Portal](https://portal.azure.com/)
2. Register a new application in Azure AD
3. Add `http://localhost:8080/callback` as redirect URI
4. Grant Calendar permissions (Calendars.Read, Calendars.ReadWrite)
5. Create client secret
6. Copy application (client) ID and secret to config

## Security Considerations

1. **Token Storage**: All OAuth tokens are encrypted using AES-256 before storage
2. **File Permissions**: Token file has 0600 permissions (owner read/write only)
3. **PKCE + State Validation**: Every authorization request includes random `state` and PKCE verifier/challenge values. These are cached in-memory by the dialog and must match the callback before any token exchange occurs.
4. **No Password Storage**: Only OAuth tokens are stored, never user passwords
5. **HTTPS Only**: All API communication uses HTTPS
6. **Token Expiration**: Tokens are checked for expiration before use
7. **Revocation**: Tokens can be revoked when disconnecting accounts

## Database Schema

### CalendarSyncStatus Table

Stores synchronization status for each connected provider:

```sql
CREATE TABLE calendar_sync_status (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,           -- google/outlook
    user_email TEXT,
    last_sync_time TIMESTAMP,
    sync_token TEXT,                  -- For incremental sync
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Error Handling

The implementation handles various error scenarios:

1. **Network Errors**: Displayed to user with retry option
2. **User Denial**: Gracefully handled, user can retry
3. **Invalid Credentials**: Clear error message displayed
4. **Token Expiration**: Automatic refresh attempted
5. **Server Errors**: Logged and displayed to user

## Testing

A test script is provided: `test_oauth_dialog.py`

```bash
python test_oauth_dialog.py
```

This opens a test window with buttons to test Google and Outlook OAuth flows.

## Limitations

1. **Local Callback Server**: Requires the configured callback port to be available
2. **Browser Required**: System must have a default browser configured
3. **Manual Configuration**: OAuth credentials must be manually configured
4. **Single Account**: Only one account per provider supported

## Future Enhancements

1. **Multiple Accounts**: Support multiple accounts per provider
2. **Automatic Token Refresh**: Background token refresh before expiration
3. **OAuth Configuration UI**: In-app OAuth credential configuration
4. **Alternative Callback Methods**: Support for other callback mechanisms
5. **Sync Conflict Resolution**: Better handling of sync conflicts

## Troubleshooting

### Callback Port Already in Use

If the configured callback port is unavailable, update the settings to use a free port:

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

Remember to update the redirect URI in your OAuth app configuration so that it matches the new port.

### Browser Doesn't Open

Ensure your system has a default browser configured. The implementation uses Python's `webbrowser` module which relies on system defaults.

### Authorization Fails

1. Check that OAuth credentials are correctly configured
2. Verify redirect URI matches in both config and OAuth app settings
3. Check that required API scopes are enabled
4. Review logs for detailed error messages

## References

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [Microsoft Graph Calendar API](https://docs.microsoft.com/en-us/graph/api/resources/calendar)
- [OAuth 2.0 Specification](https://oauth.net/2/)
