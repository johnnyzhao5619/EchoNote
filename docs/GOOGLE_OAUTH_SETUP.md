# Google OAuth Setup Guide · Google OAuth 配置指南 · Guide de configuration Google OAuth

> This document is available in English, 简体中文, and Français. Use the language sections below.

<details>
<summary><strong>English</strong></summary>

## 1. Prerequisites
- A Google account with access to the [Google Cloud Console](https://console.cloud.google.com/).
- Knowledge of where credentials are stored locally (`config/default_config.json` or `~/.echonote/config.json`). Never commit your `client_secret` to version control.

## 2. Create and Configure the Google Cloud Project
1. Sign in to the Google Cloud Console, open the project picker, and create a project (for example, “EchoNote”).
2. In the left navigation, go to **APIs & Services → Library** and enable the **Google Calendar API**.
3. Navigate to **APIs & Services → OAuth consent screen** and follow the first-time setup prompts:
   - User type: External (non-Workspace).
   - Provide the required information, such as app name “EchoNote” and a contact email.
   - Under “Scopes,” add:
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/calendar.events`
   - Under “Test users,” add your Google account and save.
4. Return to the **Credentials** page, click **+ Create Credentials → OAuth client ID**, choose “Desktop app” as the application type, name it (for example, “EchoNote Desktop”), then save and record the **Client ID** and **Client Secret** shown.

## 3. Configure Credentials in EchoNote
Choose either option below:

### Option A: Update the default configuration (recommended for development)
```json
{
  "calendar": {
    "oauth": {
      "redirect_uri": "http://localhost:8080/callback",
      "callback_port": 8080,
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
Save to `config/default_config.json`.

### Option B: Create a user-level configuration (recommended for production)
```json
{
  "calendar": {
    "oauth": {
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
Save to `~/.echonote/config.json`. When both files exist, the user-level configuration takes precedence.

> Replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with the values obtained in step 2.

## 4. Verify the Configuration
1. Confirm that `client_id` and `client_secret` are populated. Run the script below to check quickly:
   ```bash
   python - <<'PY'
   import json, pathlib
   cfg = pathlib.Path('~/.echonote/config.json').expanduser()
   data = json.load(cfg.open()) if cfg.exists() else json.load(open('config/default_config.json'))
   google = data['calendar']['oauth']['google']
   print('client_id set:', bool(google.get('client_id')))
   print('client_secret set:', bool(google.get('client_secret')))
   PY
   ```
2. Launch EchoNote (`python main.py`) and confirm under **Settings → Calendar** that no “Not configured” warning appears.

## 5. Test the OAuth Flow
1. Open the “Calendar Hub” in EchoNote.
2. Click “Connect account,” choose **Google Calendar**, and start the authorization flow.
3. A browser window should open the Google consent screen. After signing in and granting permissions, you should be redirected back to EchoNote with a success message.

## 6. FAQ
- **Why is OAuth required?** Google mandates OAuth 2.0 for applications accessing its APIs to safeguard user data.
- **Will my credentials leak?** Credentials stay on your machine. Never share your `client_secret` or commit credential files to Git.
- **Can we share credentials?** Not recommended. Each user should create their own credentials. Shared credentials require Google verification.
- **How do I revoke access?** Disconnect inside EchoNote or manage permissions at [Google Account Permissions](https://myaccount.google.com/permissions).

## 7. Security and Operations Tips
- Protect the `client_secret` and restrict file permissions (use `chmod 600`).
- Review authorized applications regularly in your Google account settings.
- Prefer test accounts and minimal scopes during development.
- If authorization fails, delete `~/.echonote/oauth_tokens.json` to force re-authorization and check `~/.echonote/logs/echonote.log` for details.

After completing these steps, EchoNote can sync and manage Google Calendar events alongside recording and transcription features.

</details>

<details>
<summary><strong>简体中文</strong></summary>

## 1. 准备工作
- 拥有可访问 [Google Cloud Console](https://console.cloud.google.com/) 的 Google 账号。
- 了解凭据将保存在本地（`config/default_config.json` 或 `~/.echonote/config.json`）。切勿将 `client_secret` 提交到版本控制。

## 2. 创建并配置 Google Cloud 项目
1. 登录 Google Cloud Console，点击顶部项目选择器并新建项目，例如“EchoNote”。
2. 在左侧菜单选择 **API 和服务 → 库**，启用 **Google Calendar API**。
3. 打开 **API 和服务 → OAuth 同意屏幕**，按照首次使用提示完成配置：
   - 用户类型：外部（非 Workspace 用户）。
   - 填写必填信息，例如应用名称“EchoNote”与联系邮箱。
   - 在“范围”中添加：
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/calendar.events`
   - 在“测试用户”中添加你的 Google 账号，保存返回。
4. 回到 **凭据** 页面，点击 **+ 创建凭据 → OAuth 客户端 ID**，应用类型选择“桌面应用”，名称可填“EchoNote Desktop”，保存并记录弹窗中的 **Client ID** 与 **Client Secret**。

## 3. 在 EchoNote 中设置凭据
可选择以下任一方式：

### 方式 A：修改默认配置（开发场景推荐）
```json
{
  "calendar": {
    "oauth": {
      "redirect_uri": "http://localhost:8080/callback",
      "callback_port": 8080,
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
保存到 `config/default_config.json`。

### 方式 B：创建用户级配置（生产场景推荐）
```json
{
  "calendar": {
    "oauth": {
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
保存到 `~/.echonote/config.json`。若两者同时存在，则用户级配置优先生效。

> 请将示例中的 `YOUR_CLIENT_ID` 与 `YOUR_CLIENT_SECRET` 替换为第 2 步获得的实际值。

## 4. 验证配置
1. 确认配置文件中 `client_id`、`client_secret` 字段非空。可使用以下脚本快速检查：
   ```bash
   python - <<'PY'
   import json, pathlib
   cfg = pathlib.Path('~/.echonote/config.json').expanduser()
   data = json.load(cfg.open()) if cfg.exists() else json.load(open('config/default_config.json'))
   google = data['calendar']['oauth']['google']
   print('client_id set:', bool(google.get('client_id')))
   print('client_secret set:', bool(google.get('client_secret')))
   PY
   ```
2. 启动 EchoNote（`python main.py`），在 **设置 → 日历** 中确认不再提示“未配置”。

## 5. 测试 OAuth 流程
1. 打开 EchoNote 的“日历中心”。
2. 点击“连接账户”，选择 **Google Calendar** 并开始授权。
3. 浏览器会打开 Google 授权页面，登录后授予权限，完成后会返回 EchoNote 并提示授权成功。

## 6. 常见问题
- **为什么必须配置 OAuth？** Google 要求所有访问其 API 的应用使用 OAuth 2.0，以保护用户数据安全。
- **凭据会泄露吗？** 凭据仅保存在本地。请勿分享 `client_secret` 或将包含凭据的文件提交到 Git。
- **可以共用凭据吗？** 不建议。每个用户应创建自己的凭据；若需公共凭据，需通过 Google 验证流程。
- **如何撤销授权？** 在 EchoNote 中点击“断开连接”，或前往 [Google 账户权限管理](https://myaccount.google.com/permissions) 移除 EchoNote。

## 7. 安全与运维建议
- 妥善保管 `client_secret`，并为包含凭据的文件设置严格权限（推荐 `chmod 600`）。
- 定期在 Google 账户设置中检查已授权的应用。
- 开发时优先使用测试账号与最小化的 API 范围。
- 遇到授权异常，可删除 `~/.echonote/oauth_tokens.json` 强制重新授权，并查看 `~/.echonote/logs/echonote.log` 获取更多信息。

完成以上步骤后，EchoNote 即可使用 Google Calendar 同步、查看事件，并结合录制与转录功能提升日程管理效率。

</details>

<details>
<summary><strong>Français</strong></summary>

## 1. Prérequis
- Un compte Google avec accès à la [Console Google Cloud](https://console.cloud.google.com/).
- Savoir où les identifiants sont stockés localement (`config/default_config.json` ou `~/.echonote/config.json`). Ne committez jamais votre `client_secret` dans le contrôle de version.

## 2. Créer et configurer le projet Google Cloud
1. Connectez-vous à la Console Google Cloud, ouvrez le sélecteur de projet et créez un nouveau projet (par exemple « EchoNote »).
2. Dans le menu de gauche, allez dans **APIs & Services → Library** et activez l’API **Google Calendar**.
3. Rendez-vous sur **APIs & Services → OAuth consent screen** et complétez l’assistant de première configuration :
   - Type d’utilisateur : Externe (hors Workspace).
   - Fournissez les informations requises, telles que le nom de l’application « EchoNote » et une adresse e-mail de contact.
   - Dans « Scopes », ajoutez :
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/calendar.events`
   - Dans « Test users », ajoutez votre compte Google puis enregistrez.
4. Revenez à la page **Credentials**, cliquez sur **+ Create Credentials → OAuth client ID**, choisissez « Desktop app » comme type d’application, nommez-la (par exemple « EchoNote Desktop »), puis enregistrez et notez le **Client ID** et le **Client Secret** affichés.

## 3. Configurer les identifiants dans EchoNote
Choisissez l’une des options suivantes :

### Option A : Mettre à jour la configuration par défaut (recommandé en développement)
```json
{
  "calendar": {
    "oauth": {
      "redirect_uri": "http://localhost:8080/callback",
      "callback_port": 8080,
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
Enregistrez dans `config/default_config.json`.

### Option B : Créer une configuration utilisateur (recommandé en production)
```json
{
  "calendar": {
    "oauth": {
      "google": {
        "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
        "client_secret": "YOUR_CLIENT_SECRET"
      }
    }
  }
}
```
Enregistrez dans `~/.echonote/config.json`. Lorsque les deux fichiers existent, la configuration utilisateur prévaut.

> Remplacez `YOUR_CLIENT_ID` et `YOUR_CLIENT_SECRET` par les valeurs obtenues à l’étape 2.

## 4. Vérifier la configuration
1. Vérifiez que `client_id` et `client_secret` sont remplis. Exécutez le script suivant pour un contrôle rapide :
   ```bash
   python - <<'PY'
   import json, pathlib
   cfg = pathlib.Path('~/.echonote/config.json').expanduser()
   data = json.load(cfg.open()) if cfg.exists() else json.load(open('config/default_config.json'))
   google = data['calendar']['oauth']['google']
   print('client_id set:', bool(google.get('client_id')))
   print('client_secret set:', bool(google.get('client_secret')))
   PY
   ```
2. Lancez EchoNote (`python main.py`) et vérifiez dans **Settings → Calendar** qu’aucun message « Non configuré » n’apparaît.

## 5. Tester le flux OAuth
1. Ouvrez le « Centre de calendrier » dans EchoNote.
2. Cliquez sur « Connecter un compte », choisissez **Google Calendar** et démarrez l’autorisation.
3. Une fenêtre de navigateur doit afficher l’écran de consentement Google. Après connexion et validation des autorisations, vous serez redirigé vers EchoNote avec un message de réussite.

## 6. FAQ
- **Pourquoi OAuth est-il requis ?** Google impose OAuth 2.0 pour les applications accédant à ses API afin de protéger les données utilisateur.
- **Mes identifiants peuvent-ils fuiter ?** Ils restent sur votre machine. Ne partagez jamais votre `client_secret` ni n’ajoutez aux commits des fichiers contenant ces informations.
- **Peut-on partager des identifiants ?** Ce n’est pas recommandé. Chaque utilisateur doit créer ses propres identifiants. Des identifiants partagés nécessitent la validation Google.
- **Comment révoquer l’accès ?** Déconnectez-vous depuis EchoNote ou gérez les autorisations sur [Google Account Permissions](https://myaccount.google.com/permissions).

## 7. Conseils de sécurité et d’exploitation
- Protégez le `client_secret` et limitez les permissions des fichiers (utilisez `chmod 600`).
- Vérifiez régulièrement les applications autorisées dans votre compte Google.
- Préférez des comptes de test et des scopes minimaux pendant le développement.
- En cas d’échec d’autorisation, supprimez `~/.echonote/oauth_tokens.json` pour forcer une nouvelle autorisation et consultez `~/.echonote/logs/echonote.log` pour plus de détails.

Après ces étapes, EchoNote peut synchroniser et gérer les événements Google Calendar tout en tirant parti des fonctionnalités d’enregistrement et de transcription.

</details>
