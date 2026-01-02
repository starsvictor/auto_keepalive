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
            'parse_mode': 'HTML'
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                print('✅ Telegram 消息发送成功')
            else:
                print(f"❌ 发送 Telegram 消息失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ 发送 Telegram 消息时出错: {e}")

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

            # 等待登录表单加载
            await page.waitForSelector('#id_username', {'visible': True, 'timeout': 10000})
            await page.waitForSelector('#id_password', {'visible': True, 'timeout': 10000})

            # 清空并输入账号和密码（使用 evaluate 直接设置 value，更可靠）
            await page.evaluate(f'''() => {{
                document.querySelector('#id_username').value = '{username}';
                document.querySelector('#id_password').value = '{password}';
            }}''')

            # 等待表单加载完成
            await asyncio.sleep(1)

            # 尝试新的登录按钮选择器（优先使用 data-login-form 属性）
            login_button = None
            selectors = [
                'form[data-login-form] button[type="submit"]',  # 新网页结构
                'button[type="submit"]',
                'button.button--primary',
                'input[type="submit"]',
                '#submit'
            ]

            for selector in selectors:
                try:
                    login_button = await page.querySelector(selector)
                    if login_button:
                        # 等待按钮可见
                        await page.waitForSelector(selector, {'visible': True, 'timeout': 5000})
                        print(f'找到登录按钮: {selector}')
                        break
                except:
                    continue

            if not login_button:
                raise Exception('无法找到登录按钮')

            # 使用 Promise.all 并发执行点击和等待跳转（更稳定）
            await asyncio.gather(
                page.waitForNavigation({'waitUntil': 'domcontentloaded'}),
                page.evaluate('(button) => button.click()', login_button)
            )

            # 等待页面加载完成
            await asyncio.sleep(2)

            # 判断是否登录成功（多重判断）
            current_url = page.url or ''
            page_title = await page.title() or ''

            # 检查登出按钮是否存在
            logout_button = await page.querySelector('a[href="/logout/"]')

            # 检查页面内容中的成功指标
            page_content = await page.content() or ''
            success_indicators = ['dashboard', 'panel', 'account', 'welcome', 'strona główna', 'logged', 'profile']
            error_indicators = ['error', 'błąd', 'invalid', 'failed', 'unauthorized', 'forbidden']

            # 判断登录是否成功（优先级从高到低）
            is_logged_in = False

            # 方法1: 检查登出按钮（最可靠的判断方式）
            if logout_button:
                is_logged_in = True
                print(f'✅ 检测到登出按钮，登录成功')
                return is_logged_in  # 直接返回，不再检查错误信息

            # 方法2: 检查 URL 中的成功指标
            if any(indicator in current_url.lower() for indicator in success_indicators):
                is_logged_in = True
                print(f'✅ URL 包含成功指标，登录成功: {current_url}')
                return is_logged_in

            # 方法3: 检查页面标题
            if any(indicator in page_title.lower() for indicator in success_indicators):
                is_logged_in = True
                print(f'✅ 页面标题包含成功指标，登录成功: {page_title}')
                return is_logged_in

            # 方法4: 检查页面内容
            if any(indicator in page_content.lower() for indicator in success_indicators):
                is_logged_in = True
                print(f'✅ 页面内容包含成功指标，登录成功')
                return is_logged_in

            # 方法5: 检查是否有错误信息（只有在没有成功指标时才检查）
            if any(indicator in page_content.lower() for indicator in error_indicators):
                is_logged_in = False
                print(f'❌ 页面包含错误信息，登录失败')
                return is_logged_in

            # 如果没有明确的成功或失败指标，返回 False
            print(f'⚠️ 无法确定登录状态，URL: {current_url}')
            return False

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

    def notify(self, email: str, success: bool, error: str = ""):
        """发送通知"""
        if not self.tg.enabled:
            return

        msg = f"""<b>ClawCloud 自动登录</b>

<b>状态:</b> {"✅ 成功" if success else "❌ 失败"}
<b>用户:</b> {email}
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

    async def login_account(self, username: str, password: str) -> bool:
        """
        登录单个 ClawCloud 账号

        Args:
            username: GitHub 用户名
            password: GitHub 密码

        Returns:
            bool: 登录是否成功
        """
        self.logs = []
        self.screenshots = []
        self.screenshot_count = 0

        self.log(f'正在登录账号: {username}')

        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()

                try:
                    # 访问 ClawCloud
                    self.log("步骤1: 打开 ClawCloud", "STEP")
                    await page.goto(SIGNIN_URL, timeout=60000)
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    await asyncio.sleep(2)
                    await page.screenshot(path=f"{self.screenshot_count:02d}_clawcloud.png")
                    self.screenshots.append(f"{self.screenshot_count:02d}_clawcloud.png")
                    self.screenshot_count += 1

                    if 'signin' not in page.url.lower():
                        self.log("已登录！", "SUCCESS")
                        self.notify(username, True)
                        print('\n✅ ClawCloud 登录成功!\n')
                        return True

                    # 点击 GitHub 登录
                    self.log("步骤2: 点击 GitHub 登录", "STEP")
                    try:
                        await page.locator('button.chakra-button:has-text("GitHub")').first.click()
                    except:
                        try:
                            await page.locator('button:has-text("GitHub")').first.click()
                        except:
                            try:
                                await page.locator('a:has-text("GitHub")').first.click()
                            except:
                                self.log("找不到 GitHub 登录按钮", "ERROR")
                                self.notify(username, False, "找不到 GitHub 登录按钮")
                                return False

                    await asyncio.sleep(3)
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    self.screenshot_count += 1
                    await page.screenshot(path=f"{self.screenshot_count:02d}_点击GitHub后.png")
                    self.screenshots.append(f"{self.screenshot_count:02d}_点击GitHub后.png")

                    # GitHub 登录
                    if 'github.com' in page.url:
                        self.log("步骤3: GitHub 账号登录", "STEP")
                        self.screenshot_count += 1
                        await page.screenshot(path=f"{self.screenshot_count:02d}_github_登录页.png")
                        self.screenshots.append(f"{self.screenshot_count:02d}_github_登录页.png")

                        # 输入用户名和密码
                        try:
                            await page.locator('input[name="login"]').fill(username)
                            await page.locator('input[name="password"]').fill(password)
                            await page.locator('input[type="submit"][value="Sign in"]').click()
                            await asyncio.sleep(3)
                            await page.wait_for_load_state('networkidle', timeout=30000)
                            self.screenshot_count += 1
                            await page.screenshot(path=f"{self.screenshot_count:02d}_github_登录后.png")
                            self.screenshots.append(f"{self.screenshot_count:02d}_github_登录后.png")
                        except Exception as e:
                            self.log(f"GitHub 登录失败: {e}", "ERROR")
                            self.notify(username, False, f"GitHub 登录失败: {e}")
                            return False

                        # 处理两步验证（如果需要）
                        if 'sessions/two-factor' in page.url or 'two_factor' in page.url:
                            self.log(f"检测到两步验证", "WARN")
                            self.screenshot_count += 1
                            f_2fa = f"{self.screenshot_count:02d}_github_2fa.png"
                            await page.screenshot(path=f_2fa)
                            self.screenshots.append(f_2fa)

                            # 尝试 TOTP 自动填充
                            totp_secret = os.getenv('TOTP_SECRET')
                            if totp_secret:
                                try:
                                    import pyotp
                                    totp = pyotp.TOTP(totp_secret)
                                    code = totp.now()
                                    self.log(f"使用 TOTP 自动填充验证码", "INFO")
                                    await page.locator('input[name="otp"]').fill(code)
                                    await page.locator('button[type="submit"]').click()
                                    await asyncio.sleep(3)
                                    await page.wait_for_load_state('networkidle', timeout=30000)

                                    if 'two-factor' not in page.url and 'two_factor' not in page.url:
                                        self.log("TOTP 验证成功", "SUCCESS")
                                        self.tg.send("✅ <b>TOTP 两步验证成功</b>")
                                    else:
                                        self.log("TOTP 验证失败，等待手动输入", "WARN")
                                        raise Exception("TOTP failed")
                                except ImportError:
                                    self.log("未安装 pyotp，需要手动验证", "WARN")
                                    raise Exception("pyotp not installed")
                                except Exception as e:
                                    self.log(f"TOTP 自动填充失败: {e}，等待手动输入", "WARN")

                            # 如果 TOTP 失败或未配置，等待手动输入
                            if 'two-factor' in page.url or 'two_factor' in page.url:
                                self.tg.send(f"⚠️ <b>需要 GitHub 两步验证</b>\n\n请在 {TWO_FACTOR_WAIT} 秒内完成")
                                self.tg.send_photo(f_2fa, "GitHub 两步验证页面")

                                for i in range(TWO_FACTOR_WAIT):
                                    await asyncio.sleep(1)
                                    if i % 10 == 0:
                                        await page.reload(timeout=10000)
                                        if 'two-factor' not in page.url and 'two_factor' not in page.url:
                                            self.log("2FA 验证成功", "SUCCESS")
                                            break
                                else:
                                    self.log("2FA 验证超时", "ERROR")
                                    self.notify(username, False, "2FA 验证超时")
                                    return False

                        # 处理设备验证（如果需要）
                        if 'sessions/verified-device' in page.url:
                            self.log(f"需要设备验证，等待 {DEVICE_VERIFY_WAIT} 秒...", "WARN")
                            self.screenshot_count += 1
                            f_device = f"{self.screenshot_count:02d}_github_device.png"
                            await page.screenshot(path=f_device)
                            self.screenshots.append(f_device)
                            self.tg.send(f"⚠️ <b>需要 GitHub 设备验证</b>\n\n请在 {DEVICE_VERIFY_WAIT} 秒内完成")
                            self.tg.send_photo(f_device, "GitHub 设备验证页面")

                            for i in range(DEVICE_VERIFY_WAIT):
                                await asyncio.sleep(1)
                                if i % 10 == 0:
                                    await page.reload(timeout=10000)
                                    if 'verified-device' not in page.url:
                                        self.log("设备验证成功", "SUCCESS")
                                        break
                            else:
                                self.log("设备验证超时", "ERROR")
                                self.notify(username, False, "设备验证超时")
                                return False

                    # 等待重定向
                    self.log("步骤4: 等待重定向", "STEP")
                    for i in range(60):
                        if 'claw.cloud' in page.url and 'signin' not in page.url.lower():
                            self.log("重定向成功！", "SUCCESS")
                            break
                        await asyncio.sleep(1)
                    else:
                        self.log("重定向超时", "ERROR")
                        self.notify(username, False, "重定向超时")
                        return False

                    self.screenshot_count += 1
                    await page.screenshot(path=f"{self.screenshot_count:02d}_完成.png")
                    self.screenshots.append(f"{self.screenshot_count:02d}_完成.png")
                    self.notify(username, True)
                    print('\n✅ ClawCloud 登录成功!\n')
                    return True

                except Exception as e:
                    self.log(f"异常: {e}", "ERROR")
                    self.screenshot_count += 1
                    await page.screenshot(path=f"{self.screenshot_count:02d}_异常.png")
                    self.screenshots.append(f"{self.screenshot_count:02d}_异常.png")
                    self.notify(username, False, str(e))
                    return False

                finally:
                    await browser.close()

        except ImportError:
            self.log("未安装 playwright，跳过 ClawCloud 登录", "WARN")
            self.log("安装命令: pip install playwright && playwright install chromium", "INFO")
            return False
        except Exception as e:
            self.log(f"ClawCloud 登录失败: {e}", "ERROR")
            return False

    async def run(self, accounts: List[Dict]) -> bool:
        """
        批量登录 ClawCloud 账号

        Args:
            accounts: 账号列表，格式 [{"username": "...", "password": "..."}]

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
            username = account.get('username')
            password = account.get('password')

            if not username or not password:
                print(f'账号 {i} 配置不完整，跳过')
                fail_count += 1
                continue

            print(f'\n[{i}/{len(accounts)}] 正在登录账号: {username}')

            try:
                is_logged_in = await self.login_account(username, password)

                if is_logged_in:
                    success_count += 1
                    print(f'✅ 账号 {username} 登录成功!')
                else:
                    fail_count += 1
                    print(f'❌ 账号 {username} 登录失败')
            except Exception as e:
                fail_count += 1
                print(f'❌ 账号 {username} 登录异常: {e}')

            # 随机延时 3-8 秒
            if i < len(accounts):
                delay = random.randint(3000, 8000)
                print(f'等待 {delay/1000:.1f} 秒后继续...\n')
                await asyncio.sleep(delay / 1000)

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
        await clawcloud.run(clawcloud_accounts)

    print('\n' + '='*60)
    print('所有保活任务完成!')
    print('='*60 + '\n')


if __name__ == '__main__':
    asyncio.run(main())
