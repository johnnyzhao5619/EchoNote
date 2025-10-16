# Google OAuth 配置指南

## 问题根源

你遇到的问题是：**Google OAuth 凭据未配置**

当你点击"连接 Google 账户"时，应用检测到 `client_id` 和 `client_secret` 为空，因此显示警告对话框而不是打开浏览器。

## 解决方案：配置 Google OAuth 凭据

### 步骤 1: 创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 登录你的 Google 账户
3. 点击顶部的项目选择器
4. 点击"新建项目"
5. 输入项目名称（例如："EchoNote"）
6. 点击"创建"

### 步骤 2: 启用 Google Calendar API

1. 在左侧菜单中，选择"API 和服务" > "库"
2. 搜索"Google Calendar API"
3. 点击"Google Calendar API"
4. 点击"启用"按钮

### 步骤 3: 创建 OAuth 2.0 凭据

1. 在左侧菜单中，选择"API 和服务" > "凭据"
2. 点击顶部的"+ 创建凭据"
3. 选择"OAuth 客户端 ID"

#### 首次创建需要配置同意屏幕：

4. 点击"配置同意屏幕"
5. 选择"外部"（如果你不是 Google Workspace 用户）
6. 点击"创建"
7. 填写必填信息：
   - 应用名称：EchoNote
   - 用户支持电子邮件：你的邮箱
   - 开发者联系信息：你的邮箱
8. 点击"保存并继续"
9. 在"范围"页面，点击"添加或移除范围"
10. 搜索并添加以下范围：
    - `https://www.googleapis.com/auth/calendar.readonly`
    - `https://www.googleapis.com/auth/calendar.events`
11. 点击"更新" > "保存并继续"
12. 在"测试用户"页面，添加你的 Google 账户邮箱
13. 点击"保存并继续"
14. 点击"返回到控制台"

#### 创建 OAuth 客户端 ID：

15. 再次点击"+ 创建凭据" > "OAuth 客户端 ID"
16. 应用类型：选择"桌面应用"
17. 名称：输入"EchoNote Desktop"
18. 点击"创建"

### 步骤 4: 获取凭据

1. 创建成功后，会显示一个对话框
2. 复制 **客户端 ID**（类似：`123456789-abc.apps.googleusercontent.com`）
3. 复制 **客户端密钥**（类似：`GOCSPX-abc123def456`）
4. 点击"确定"

### 步骤 5: 配置 EchoNote

有两种方式配置凭据：

#### 方式 1: 修改默认配置文件（推荐用于开发）

编辑 `config/default_config.json`：

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

#### 方式 2: 创建用户配置文件（推荐用于生产）

创建 `~/.echonote/config.json`：

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

**注意**: 将 `YOUR_CLIENT_ID` 和 `YOUR_CLIENT_SECRET` 替换为你在步骤 4 中复制的实际值。

### 步骤 6: 验证配置

1. 确认配置文件包含非空凭据。示例命令：
   ```bash
   python - <<'PY'
   import json, pathlib
   cfg = pathlib.Path('~/.echonote/config.json').expanduser()
   data = json.load(cfg.open()) if cfg.exists() else json.load(open('config/default_config.json'))
   google = data['calendar']['oauth']['google']
   print('client_id:', bool(google.get('client_id')))
   print('client_secret:', bool(google.get('client_secret')))
   PY
   ```
   输出 `True` 表示字段已填入。
2. 重启 EchoNote，打开 **设置 → 日历**。界面若不再提示“未配置”即说明凭据被正确加载。
3. 如仍显示未配置，请检查 JSON 格式、文件权限（建议 `600`）或路径是否写错。

### 步骤 7: 测试 OAuth 连接

1. 启动 EchoNote：`python main.py`
2. 进入"日历中心"页面
3. 点击"连接账户"按钮
4. 选择"Google Calendar"
5. 点击"Start Authorization"
6. 浏览器应该会打开 Google 授权页面
7. 登录并授权 EchoNote 访问你的日历
8. 授权成功后，浏览器会重定向回应用
9. 应用会显示"Authorization successful!"

## 常见问题

### Q: 为什么需要创建 OAuth 凭据？

A: Google 要求所有访问其 API 的应用都必须使用 OAuth 2.0 进行身份验证。这确保了用户数据的安全性。

### Q: 我的凭据会被泄露吗？

A: 凭据存储在本地配置文件中，不会上传到任何服务器。但请注意：

- 不要将包含凭据的配置文件提交到 Git
- 不要与他人分享你的 client_secret

### Q: 我可以使用别人的凭据吗？

A: 不建议。每个用户应该创建自己的 OAuth 凭据。如果你是应用开发者，可以为应用创建一个公共凭据，但需要通过 Google 的验证流程。

### Q: 授权后需要重新配置吗？

A: 不需要。授权成功后，访问令牌会被安全存储，下次启动应用时会自动使用。

### Q: 如何撤销授权？

A: 有两种方式：

1. 在 EchoNote 中点击"断开连接"
2. 访问 [Google 账户安全设置](https://myaccount.google.com/permissions) 并撤销 EchoNote 的访问权限

## 安全提示

1. **保护你的 client_secret**: 不要分享或公开
2. **定期检查授权**: 在 Google 账户设置中查看已授权的应用
3. **使用测试账户**: 开发时使用测试 Google 账户
4. **限制范围**: 只请求必要的权限（我们只请求日历访问）

## 下一步

配置完成后，你可以：

1. 连接 Google Calendar
2. 同步日历事件
3. 在时间线中查看事件
4. 为事件自动启动录制和转录

## 需要帮助？

如果遇到问题，请：

1. 检查 `~/.echonote/logs/echonote.log` 中是否有 OAuth 相关错误信息。
2. 确认配置文件 JSON 格式正确且凭据未留空。
3. 重新启动 EchoNote 并再次尝试连接，必要时删除旧的 `~/.echonote/oauth_tokens.json` 以强制重新授权。
4. 若问题仍在，请提交 issue 并附上日志与错误截图。
