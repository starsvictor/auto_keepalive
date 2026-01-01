#!/usr/bin/env python3
"""
Serv00 & ClawCloud 统一保活脚本
支持多账号批量登录，自动发送 Telegram 通知
"""

import json
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random

# 异步库
import aiofiles
from pyppeteer import launch

# 同步库
import requests

# ==================== 配置 ====================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ClawCloud 配置
CLAW_CLOUD_URL = "https://us-west-1.run.claw.cloud"
SIGNIN_URL = f"{CLAW_CLOUD_URL}/signin"
DEVICE_VERIFY_WAIT = 80
TWO_FACTOR_WAIT = 60


# ==================== 工具类 ====================
class Telegram:
    """Telegram 通知工具"""

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            print('未配置 Telegram Bot Token 或 Chat ID，跳过通知')

    def send(self, message: str):
        """发送文本消息"""
        if not self.enabled:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'reply_markup': {
                'inline_keyboard': [
                    [{'text': '问题反馈❓', 'url': 'https://t.me/yxjsjl'}]
                ]
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code != 200:
                print(f"发送 Telegram 消息失败: {response.text}")
        except Exception as e:
            print(f"发送 Telegram 消息时出错: {e}")

    def send_photo(self, photo_path: str, caption: str = ""):
        """发送图片"""
        if not self.enabled or not os.path.exists(photo_path):
            return

        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"

        try:
            with open(photo_path, 'rb') as f:
                files = {'photo': f}
                data = {'chat_id': self.chat_id, 'caption': caption[:1024]}
                response = requests.post(url, data=data, files=files, timeout=60)

                if response.status_code != 200:
                    print(f"发送图片失败: {response.text}")
        except Exception as e:
            print(f"发送图片时出错: {e}")


def format_to_iso(date):
    """格式化日期为 ISO 格式字符串"""
    return date.strftime('%Y-%m-%d %H:%M:%S')


async def delay_time(ms):
    """延时函数，单位毫秒"""
    await asyncio.sleep(ms / 1000)


# ==================== Serv00 登录 ====================
class Serv00Login:
    """Serv00/CT8 登录处理"""

    def __init__(self, telegram: Telegram):
        self.tg = telegram
        self.browser = None
        self.message = ''

    async def login_account(self, username: str, password: str, panelnum: str) -> bool:
        """
        登录单个 Serv00 账号

        Args:
            username: 用户名
            password: 密码
            panelnum: 面板编号

        Returns:
            bool: 登录是否成功
        """
        page = None
        try:
            # 如果浏览器未启动，则启动浏览器
            if not self.browser:
                self.browser = await launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )

            page = await self.browser.newPage()
            url = f'https://panel{panelnum}.serv00.com/login/?next=/'
            await page.goto(url)

            # 清空用户名输入框
            username_input = await page.querySelector('#id_username')
            if username_input:
                await page.evaluate('(input) => input.value = ""', username_input)

            # 输入账号和密码
            await page.type('#id_username', username)
            await page.type('#id_password', password)

            # 点击登录按钮
            login_button = await page.querySelector('#submit')
            if login_button:
                await login_button.click()
            else:
                raise Exception('无法找到登录按钮')

            # 等待页面跳转
            await page.waitForNavigation()

            # 判断是否登录成功
            is_logged_in = await page.evaluate('''() => {
                const logoutButton = document.querySelector('a[href="/logout/"]');
                return logoutButton !== null;
            }''')

            return is_logged_in

        except Exception as e:
            print(f'账号 {username} 登录时出现错误: {e}')
            return False

        finally:
            if page:
                await page.close()

    async def run(self, accounts: List[Dict]):
        """
        批量登录 Serv00 账号

        Args:
            accounts: 账号列表，格式 [{"username": "...", "password": "...", "panelnum": "..."}]
        """
        if not accounts:
            print('没有 Serv00 账号需要登录')
            return

        print('\n' + '='*50)
        print('开始 Serv00/CT8 账号登录')
        print('='*50 + '\n')

        self.message = '<b>Serv00/CT8 自动登录</b>\n\n'

        for account in accounts:
            username = account['username']
            password = account['password']
            panelnum = account['panelnum']

            print(f'正在登录账号: {username} (panel{panelnum})')
            is_logged_in = await self.login_account(username, password, panelnum)

            if is_logged_in:
                now_utc = format_to_iso(datetime.utcnow())
                now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
                success_msg = f'✅ 账号 {username} 于北京时间 {now_beijing}(UTC {now_utc})登录成功!'
                self.message += success_msg + '\n'
                print(success_msg)
            else:
                fail_msg = f'❌ 账号 {username} 登录失败，请检查账号和密码'
                self.message += fail_msg + '\n'
                print(fail_msg)

            # 随机延时 1-8 秒
            delay = random.randint(1000, 8000)
            print(f'等待 {delay/1000:.1f} 秒后继续...\n')
            await delay_time(delay)

        # 关闭浏览器
        if self.browser:
            await self.browser.close()
            self.browser = None

        self.message += '\n所有 Serv00 账号登录完成!'
        print('='*50)
        print('Serv00 登录完成!')
        print('='*50 + '\n')

        # 发送通知
        self.tg.send(self.message)


# ==================== ClawCloud 登录 ====================
class ClawCloudLogin:
    """ClawCloud 登录处理（使用 Playwright 同步 API）"""

    def __init__(self, telegram: Telegram):
        self.tg = telegram
        self.logs = []
        self.screenshots = []
        self.screenshot_count = 0
        self.browser = None
        self.context = None

    def log(self, msg: str, level: str = "INFO"):
        """记录日志"""
        icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARN": "⚠️",
            "STEP": "🔹"
        }
        line = f"{icons.get(level, '•')} {msg}"
        print(line)
        self.logs.append(line)

    def screenshot(self, page, name: str) -> str:
        """截图"""
        self.screenshot_count += 1
        filename = f"{self.screenshot_count:02d}_{name}.png"
        try:
            page.screenshot(path=filename)
            self.screenshots.append(filename)
        except:
            pass
        return filename

    def notify(self, success: bool, error: str = ""):
        """发送通知"""
        if not self.tg.enabled:
            return

        msg = f"""<b>ClawCloud 自动登录</b>

<b>状态:</b> {"✅ 成功" if success else "❌ 失败"}
<b>用户:</b> {self.username}
<b>时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"""

        if error:
            msg += f"\n<b>错误:</b> {error}"

        msg += "\n\n<b>日志:</b>\n" + "\n".join(self.logs[-6:])

        self.tg.send(msg)

        # 发送截图
        if self.screenshots:
            if not success:
                for s in self.screenshots[-3:]:
                    self.tg.send_photo(s, s)
            else:
                self.tg.send_photo(self.screenshots[-1], "登录完成")

    def login_account(self, email: str, password: str) -> bool:
        """
        登录单个 ClawCloud 账号

        Args:
            email: Google 邮箱
            password: Google 密码

        Returns:
            bool: 登录是否成功
        """
        self.logs = []
        self.screenshots = []
        self.screenshot_count = 0

        self.log(f'正在登录账号: {email}')

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()

                try:
                    # 访问 ClawCloud
                    self.log("步骤1: 打开 ClawCloud", "STEP")
                    page.goto(SIGNIN_URL, timeout=60000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    time.sleep(2)
                    self.screenshot(page, "clawcloud")

                    if 'signin' not in page.url.lower():
                        self.log("已登录！", "SUCCESS")
                        self.notify(True)
                        print('\n✅ ClawCloud 登录成功!\n')
                        return True

                    # 点击 Google 登录
                    self.log("步骤2: 点击 Google 登录", "STEP")
                    try:
                        page.locator('button:has-text("Google")').first.click()
                    except:
                        try:
                            page.locator('a:has-text("Google")').first.click()
                        except:
                            self.log("找不到 Google 登录按钮", "ERROR")
                            self.notify(False, "找不到 Google 登录按钮")
                            return False

                    time.sleep(3)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    self.screenshot(page, "点击Google后")

                    # Google 登录
                    if 'accounts.google.com' in page.url:
                        self.log("步骤3: Google 账号登录", "STEP")
                        self.screenshot(page, "google_登录页")

                        # 输入邮箱
                        try:
                            page.locator('input[type="email"]').fill(email)
                            page.locator('button:has-text("下一步"), button:has-text("Next")').first.click()
                            time.sleep(3)
                            page.wait_for_load_state('networkidle', timeout=30000)
                            self.screenshot(page, "google_输入邮箱后")
                        except Exception as e:
                            self.log(f"输入邮箱失败: {e}", "ERROR")
                            self.notify(False, f"输入邮箱失败: {e}")
                            return False

                        # 输入密码
                        try:
                            page.locator('input[type="password"]').fill(password)
                            page.locator('button:has-text("下一步"), button:has-text("Next")').first.click()
                            time.sleep(3)
                            page.wait_for_load_state('networkidle', timeout=30000)
                            self.screenshot(page, "google_输入密码后")
                        except Exception as e:
                            self.log(f"输入密码失败: {e}", "ERROR")
                            self.notify(False, f"输入密码失败: {e}")
                            return False

                        # 处理两步验证（如果需要）
                        if 'challenge' in page.url or 'signin/v2/challenge' in page.url:
                            self.log(f"需要两步验证，等待 {TWO_FACTOR_WAIT} 秒...", "WARN")
                            f_2fa = self.screenshot(page, "google_2fa")
                            self.tg.send(f"⚠️ <b>需要 Google 两步验证</b>\n\n请在 {TWO_FACTOR_WAIT} 秒内完成")
                            self.tg.send_photo(f_2fa, "Google 两步验证页面")

                            for i in range(TWO_FACTOR_WAIT):
                                time.sleep(1)
                                if i % 10 == 0:
                                    page.reload(timeout=10000)
                                    if 'challenge' not in page.url:
                                        self.log("2FA 验证成功", "SUCCESS")
                                        break
                            else:
                                self.log("2FA 验证超时", "ERROR")
                                self.notify(False, "2FA 验证超时")
                                return False

                    # 等待重定向
                    self.log("步骤4: 等待重定向", "STEP")
                    for i in range(60):
                        if 'claw.cloud' in page.url and 'signin' not in page.url.lower():
                            self.log("重定向成功！", "SUCCESS")
                            break
                        time.sleep(1)
                    else:
                        self.log("重定向超时", "ERROR")
                        self.notify(False, "重定向超时")
                        return False

                    self.screenshot(page, "完成")
                    self.notify(True)
                    print('\n✅ ClawCloud 登录成功!\n')
                    return True

                except Exception as e:
                    self.log(f"异常: {e}", "ERROR")
                    self.screenshot(page, "异常")
                    self.notify(False, str(e))
                    return False

                finally:
                    browser.close()

        except ImportError:
            self.log("未安装 playwright，跳过 ClawCloud 登录", "WARN")
            self.log("安装命令: pip install playwright && playwright install chromium", "INFO")
            return False
        except Exception as e:
            self.log(f"ClawCloud 登录失败: {e}", "ERROR")
            return False

    def run(self, accounts: List[Dict]) -> bool:
        """
        批量登录 ClawCloud 账号

        Args:
            accounts: 账号列表，格式 [{"email": "...", "password": "..."}]

        Returns:
            bool: 是否至少有一个账号登录成功
        """
        if not accounts:
            print('没有 ClawCloud 账号需要登录')
            return False

        print('\n' + '='*50)
        print('开始 ClawCloud 登录')
        print('='*50 + '\n')

        success_count = 0
        fail_count = 0

        for i, account in enumerate(accounts, 1):
            email = account.get('email')
            password = account.get('password')

            if not email or not password:
                print(f'账号 {i} 配置不完整，跳过')
                fail_count += 1
                continue

            print(f'\n[{i}/{len(accounts)}] 正在登录账号: {email}')

            try:
                is_logged_in = self.login_account(email, password)

                if is_logged_in:
                    success_count += 1
                    print(f'✅ 账号 {email} 登录成功!')
                else:
                    fail_count += 1
                    print(f'❌ 账号 {email} 登录失败')
            except Exception as e:
                fail_count += 1
                print(f'❌ 账号 {email} 登录异常: {e}')

            # 随机延时 3-8 秒
            if i < len(accounts):
                delay = random.randint(3000, 8000)
                print(f'等待 {delay/1000:.1f} 秒后继续...\n')
                time.sleep(delay / 1000)

        print('\n' + '='*50)
        print(f'ClawCloud 登录完成! 成功: {success_count}, 失败: {fail_count}')
        print('='*50 + '\n')

        # 发送汇总通知
        if self.tg.enabled:
            summary = f"""<b>ClawCloud 批量登录完成</b>

<b>总计:</b> {len(accounts)} 个账号
<b>成功:</b> {success_count}
<b>失败:</b> {fail_count}
<b>时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"""
            self.tg.send(summary)

        return success_count > 0


# ==================== 主程序 ====================
async def main():
    """主函数"""
    print('\n' + '='*60)
    print('Serv00 & ClawCloud 统一保活脚本')
    print('='*60 + '\n')

    # 初始化 Telegram
    telegram = Telegram()

    # 读取 Serv00 账号配置
    serv00_accounts = []
    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        serv00_accounts = json.loads(accounts_json)
        print(f'已加载 {len(serv00_accounts)} 个 Serv00 账号')
    except FileNotFoundError:
        print('未找到 accounts.json 文件，跳过 Serv00 登录')
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')

    # 执行 Serv00 登录
    if serv00_accounts:
        serv00 = Serv00Login(telegram)
        await serv00.run(serv00_accounts)

    # 读取 ClawCloud 账号配置
    clawcloud_accounts = []
    try:
        async with aiofiles.open('clawcloud_accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        clawcloud_accounts = json.loads(accounts_json)
        print(f'已加载 {len(clawcloud_accounts)} 个 ClawCloud 账号')
    except FileNotFoundError:
        print('未找到 clawcloud_accounts.json 文件，跳过 ClawCloud 登录')
    except Exception as e:
        print(f'读取 clawcloud_accounts.json 文件时出错: {e}')

    # 执行 ClawCloud 登录
    if clawcloud_accounts:
        clawcloud = ClawCloudLogin(telegram)
        clawcloud.run(clawcloud_accounts)

    print('\n' + '='*60)
    print('所有保活任务完成!')
    print('='*60 + '\n')


if __name__ == '__main__':
    asyncio.run(main())
