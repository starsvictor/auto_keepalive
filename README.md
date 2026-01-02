# Serv00 & CT8 & ClawCloud 自动化批量保号脚本

Serv00、CT8 与 ClawCloud 自动化批量保号，每 7 天自动登录一次面板，并且发送消息到 Telegram

利用 GitHub Actions 以及 Python 脚本实现，**无需本地运行**，完全自动化

---

## 功能特性

- ✅ 支持 Serv00/CT8 多账号批量登录
- ✅ 支持 ClawCloud 多账号批量登录（GitHub 账号）
- ✅ GitHub Actions 定时自动运行（每 7 天）
- ✅ 统一的 Telegram 消息通知
- ✅ 自动处理 GitHub 两步验证和设备验证
- ✅ 详细的登录日志和进度显示
- ✅ 账号间自动延时，避免频繁请求
- ✅ 完全云端运行，无需本地环境

---

## 快速开始

### 1. Fork 仓库

1. 访问本仓库页面
2. 点击页面右上角的 **Fork** 按钮，将仓库 fork 到你的 GitHub 账户下

### 2. 配置 Telegram 通知（可选但推荐）

#### 2.1 创建 Telegram Bot

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)，创建一个新 Bot
2. 获取 Bot 的 **API Token**（格式如：`1234567890:ABCDEFghijklmnopQRSTuvwxyZ`）

#### 2.2 获取 Telegram Bot Chat ID

 在 Telegram 中找到 [@userinfobot](https://t.me/userinfobot)，向你的 Bot 发送任意消息，获得你 Telegram Bot CHAT ID

### 3. 配置 GitHub Secrets

1. 转到你 fork 的仓库页面
2. 点击 **Settings** → 左侧菜单选择 **Secrets and variables** → **Actions**
3. 点击 **New repository secret**，添加以下 Secrets：

| Secret 名称 | 说明 | 是否必需 |
|------------|------|---------|
| `SERV00_ACCOUNTS_JSON` | Serv00/CT8 账号配置（JSON 格式） | Serv00 必需 |
| `CLAWCLOUD_ACCOUNTS_JSON` | ClawCloud 账号配置（JSON 格式） | ClawCloud 必需 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 可选（推荐） |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可选（推荐） |
| `GITHUB_TOTP_SECRET` | GitHub TOTP 密钥（用于自动化两步验证） | 可选 |

#### 配置示例

**SERV00_ACCOUNTS_JSON 格式（Serv00/CT8）：**
```json
[
  {
    "username": "your_serv00_username",
    "password": "your_serv00_password",
    "panelnum": "4"
  },
  {
    "username": "your_ct8_username",
    "password": "your_ct8_password",
    "panelnum": "7"
  }
]
```

**参数说明：**
- `username`: Serv00/CT8 用户名
- `password`: 对应密码
- `panelnum`: 面板编号（如 panel4.serv00.com 中的 `4`）

**CLAWCLOUD_ACCOUNTS_JSON 格式（ClawCloud）：**
```json
[
  {
    "username": "your-github-username1",
    "password": "your-github-password1"
  },
  {
    "username": "your-github-username2",
    "password": "your-github-password2"
  }
]
```

**参数说明：**
- `username`: GitHub 用户名
- `password`: GitHub 账号密码

**注意事项：**
- 支持单个或多个账号配置
- 如果只需要保活 Serv00，只配置 `SERV00_ACCOUNTS_JSON` 即可
- 如果只需要保活 ClawCloud，只配置 `CLAWCLOUD_ACCOUNTS_JSON` 即可
- 如果启用了 GitHub 两步验证，脚本会自动等待 60 秒供你完成验证
- 如果需要设备验证，脚本会自动等待 80 秒供你完成验证

#### GitHub 两步验证自动化（可选）

如果您的 GitHub 账号启用了 TOTP 身份验证器（如 Google Authenticator、Authy），可以配置自动化：

**步骤 1：获取 TOTP 密钥**
1. 在 GitHub 设置两步验证时，会显示一个二维码
2. 点击"无法扫描？"或"输入此文本代码"
3. 复制显示的密钥（格式如：`JBSWY3DPEHPK3PXP`）

**步骤 2：配置 Secret**
1. 在 GitHub Secrets 中添加 `GITHUB_TOTP_SECRET`
2. 值为上一步复制的密钥

**支持的验证方式：**
- ✅ **TOTP 身份验证器**（Google Authenticator、Authy 等）- 可自动化
- ❌ **SMS 短信验证码** - 需要手动输入
- ❌ **GitHub Mobile 推送通知** - 需要手机批准
- ❌ **安全密钥（Hardware Key）** - 需要物理设备

**工作原理：**
- 配置 TOTP 密钥后，脚本会自动生成验证码并填入
- 如果 TOTP 验证失败或未配置，会自动回退到手动等待模式
- 手动模式下会发送 Telegram 通知并等待 60 秒

### 4. 启用 GitHub Actions

1. 进入你 fork 的仓库，点击 **Actions** 标签页
2. 如果 Actions 未自动启用，点击 **I understand my workflows, go ahead and enable them** 按钮
3. GitHub Actions 将根据定时任务（每 7 天一次）自动运行脚本
4. 也可以在 Actions 页面手动触发工作流

---

## 运行日志示例

脚本运行时会输出详细日志：

```
============================================================
Serv00 & ClawCloud 统一保活脚本
============================================================

已加载 2 个 Serv00 账号
已加载 3 个 ClawCloud 账号

==================================================
开始 Serv00/CT8 账号登录
==================================================

正在登录账号: user1 (panel4)
✅ 账号 user1 于北京时间 2026-01-01 22:30:00(UTC 2026-01-01 14:30:00)登录成功!
等待 5.2 秒后继续...

==================================================
Serv00 登录完成!
==================================================

==================================================
开始 ClawCloud 登录
==================================================

[1/3] 正在登录账号: user1@gmail.com
ℹ️ 正在登录账号: user1@gmail.com
🔹 步骤1: 打开 ClawCloud
🔹 步骤2: 点击 Google 登录
🔹 步骤3: Google 账号登录
🔹 步骤4: 等待重定向
✅ 重定向成功！
✅ 账号 user1@gmail.com 登录成功!
等待 5.2 秒后继续...

[2/3] 正在登录账号: user2@gmail.com
...

==================================================
ClawCloud 登录完成! 成功: 3, 失败: 0
==================================================

============================================================
所有保活任务完成!
============================================================
```

---

## 常见问题

### 1. 如何查看 GitHub Actions 运行日志？

进入你的仓库 → **Actions** 标签页 → 点击具体的工作流运行记录 → 查看详细日志

### 2. 为什么没有收到 Telegram 通知？

- 检查 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID` 是否配置正确
- 确认 Bot 已经启动并且你已经向它发送过消息
- 查看 Actions 运行日志中是否有错误信息

### 3. 如何修改登录频率？

编辑 [.github/workflows/Login.yml](.github/workflows/Login.yml) 文件中的 `cron` 表达式：

```yaml
schedule:
  - cron: '0 0 */7 * *'  # 每 7 天运行一次
```

常用 cron 表达式：
- `0 0 * * *` - 每天运行一次
- `0 0 */3 * *` - 每 3 天运行一次
- `0 0 */7 * *` - 每 7 天运行一次（默认）
- `0 0 */14 * *` - 每 14 天运行一次

### 4. ClawCloud 登录超时怎么办？

**问题：** GitHub 两步验证或设备验证超时

**解决：**
- 两步验证会自动等待 60 秒，请在此时间内完成
- 设备验证会自动等待 80 秒，请在此时间内完成
- 如需更长时间，可以修改脚本中的 `TWO_FACTOR_WAIT` 或 `DEVICE_VERIFY_WAIT` 参数
- 检查 GitHub 账号是否正常

### 5. Serv00 登录失败怎么办？

**问题：** 账号密码正确但登录失败

**解决：**
- 检查面板编号是否正确
- 手动访问面板确认账号状态
- 检查是否有验证码或其他验证方式

### 6. 如何配置单个账号？

JSON 文件中只配置一个账号即可：

```json
[
  {
    "username": "your-github-username",
    "password": "your-github-password"
  }
]
```

### 7. 如何只保活 Serv00 或只保活 ClawCloud？

- **只保活 Serv00：** 只配置 `SERV00_ACCOUNTS_JSON`，不配置 `CLAWCLOUD_ACCOUNTS_JSON`
- **只保活 ClawCloud：** 只配置 `CLAWCLOUD_ACCOUNTS_JSON`，不配置 `SERV00_ACCOUNTS_JSON`

---

## 注意事项

- **保密性：** Secrets 是敏感信息，请确保不要将它们泄露到公共代码库
- **更新管理：** 如需更新或删除 Secrets，可通过仓库的 Secrets 页面进行管理
- **登录频率：** 默认每 7 天自动登录一次，建议不要设置过于频繁
- **账号安全：** 建议为重要账号启用两步验证

---

## 技术架构

- **运行环境：** GitHub Actions (Ubuntu Latest)
- **Python 版本：** 3.10
- **核心库：**
  - `pyppeteer` - Serv00/CT8 登录
  - `playwright` - ClawCloud 登录
  - `aiofiles` - 异步文件操作
  - `requests` - Telegram 通知

---

## 许可证

本项目仅供学习交流使用，请勿用于非法用途。
