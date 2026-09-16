import argparse
import base64
import hashlib
import json
import logging
import os
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from tracker_db import connect, database_path, init_database, save_play_data

PROJECT_ROOT = Path(__file__).resolve().parent

# 配置日志 - 仅保留关键日志
logging.basicConfig(
    level=logging.WARNING,  # 改为WARNING级别，减少日志量
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "switch_tracker.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("switch_tracker")

# 数据库配置
DB_FILE = database_path()

def save_to_database(data):
    """将一份 API 快照幂等地保存到数据库。"""
    try:
        collected_at = datetime.now(timezone.utc).isoformat()
        save_play_data(data, collected_at, DB_FILE)
        return True
    except Exception as exc:
        logger.exception("保存数据到数据库失败: %s", exc)
        return False

def get_game_list_with_cn_names():
    """获取游戏列表，优先使用中文名称"""
    try:
        init_database(DB_FILE)
        with connect(DB_FILE) as conn:
            cursor = conn.execute('''
        SELECT games.title_id, 
               CASE WHEN games.chinese_name IS NOT NULL AND games.chinese_name != '' 
                    THEN games.chinese_name 
                    ELSE games.title_name 
               END AS display_name,
               h.total_played_days
        FROM games
        JOIN (
            SELECT title_id, MAX(total_played_days) as total_played_days
            FROM game_history
            GROUP BY title_id
        ) h ON games.title_id = h.title_id
        ORDER BY h.total_played_days DESC
        LIMIT 10
        ''')
        
            games = cursor.fetchall()
        return games
    except Exception as e:
        logger.error(f"获取游戏列表失败: {str(e)}")
        return []

class NintendoSession:
 
    def __init__(self, client_id='5c38e31cd085304b') -> None:
        self.session = requests.Session()
        self.client_id = client_id
        self.ua = 'com.nintendo.znej/1.13.0 (Android/7.1.2)'
        self.config_dir = PROJECT_ROOT / "config"
        self.token_file = self.config_dir / "tokens.json"
        self.timeout = 30  # 请求超时时间（秒）
        self.load_tokens()
 
    def load_tokens(self):
        """从配置文件加载已保存的 token"""
        if not self.config_dir.exists():
            try:
                self.config_dir.mkdir(parents=True, mode=0o700)
            except OSError as e:
                logger.error(f"创建配置目录失败: {str(e)}")
                return False
            
        if self.token_file.exists():
            try:
                with self.token_file.open("r", encoding="utf-8") as f:
                    tokens = json.load(f)
                    self.session_token = tokens.get('session_token')
                    self.access_token = tokens.get('access_token')
                    
                    # 检查token是否过期
                    if self.access_token and 'expires_in' in self.access_token:
                        expires_at = tokens.get('expires_at', 0)
                        if time.time() > expires_at:
                            logger.warning("访问令牌已过期，将使用会话令牌刷新")
                            return True
                    return True
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"读取token失败: {str(e)}")
                return False
        return False

    def save_tokens(self):
        """保存 token 到配置文件"""
        try:
            # 计算过期时间
            expires_at = 0
            if hasattr(self, 'access_token') and self.access_token and 'expires_in' in self.access_token:
                expires_at = time.time() + int(self.access_token['expires_in']) - 300  # 提前5分钟刷新
                
            tokens = {
                'session_token': getattr(self, 'session_token', None),
                'access_token': getattr(self, 'access_token', None),
                'expires_at': expires_at
            }
            
            # 确保目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary_file = self.token_file.with_suffix(".tmp")
            with temporary_file.open("w", encoding="utf-8") as file_handle:
                json.dump(tokens, file_handle)
            os.chmod(temporary_file, stat.S_IRUSR | stat.S_IWUSR)
            temporary_file.replace(self.token_file)
            return True
        except Exception as e:
            logger.error(f"保存 token 失败: {str(e)}")
            return False

    def check_tokens_valid(self):
        """检查 token 是否有效"""
        if not hasattr(self, 'access_token') or not self.access_token:
            return False
            
        try:
            url = 'https://news-api.entry.nintendo.co.jp/api/v1.1/users/me/play_histories'
            header = {
                'Authorization': f"{self.access_token['token_type']} {self.access_token['access_token']}",
                'User-Agent': self.ua,
            }
            r = self.session.get(url, headers=header, timeout=self.timeout)
            
            return r.status_code == 200
        except Exception as e:
            logger.error(f"验证令牌失败: {str(e)}")
            return False

    def log_in(self):
        '''登录 Nintendo 账号并返回 session_token'''
        # 如果已有有效的 token，直接返回
        if hasattr(self, 'session_token') and self.check_tokens_valid():
            return self.session_token

        print("注意：获取的链接有效期很短，请在 5 分钟内完成操作！")

        # 生成安全的随机验证码
        try:
            auth_code_verifier = base64.urlsafe_b64encode(os.urandom(32))
            auth_cv_hash = hashlib.sha256()
            auth_cv_hash.update(auth_code_verifier.replace(b"=", b""))
            auth_code_challenge = base64.urlsafe_b64encode(auth_cv_hash.digest())
        except Exception as e:
            logger.error(f"生成验证码失败: {str(e)}")
            return None

        app_head = {
            'Host':                      'accounts.nintendo.com',
            'Connection':                'keep-alive',
            'Cache-Control':             'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent':                'Mozilla/5.0 (Nintendo Switch; WebApplet) AppleWebKit/609.4 (KHTML, like Gecko) NF/6.0.2.15.4 NintendoBrowser/5.1.0.22433',
            'Accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language':           'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding':           'gzip, deflate, br',
            'DNT':                       '1'
        }
        body = {
            'state':                               '',
            'redirect_uri':                        f'npf{self.client_id}://auth',
            'client_id':                           self.client_id,
            'scope':                               'openid user user.mii user.email user.links[].id',
            'response_type':                       'session_token_code',
            'session_token_code_challenge':        auth_code_challenge.replace(b"=", b"").decode('utf-8'),
            'session_token_code_challenge_method': 'S256',
            'theme':                               'login_form'
        }

        url = 'https://accounts.nintendo.com/connect/1.0.0/authorize'
        try:
            r = self.session.get(url, headers=app_head, params=body, timeout=self.timeout)
        except Exception as e:
            logger.error(f"请求认证页面失败: {str(e)}")
            print(f"请求失败: {str(e)}")
            return None

        if not r.history:
            print("无法获取登录链接，请重试")
            return None

        post_login = r.history[0].url

        print("\n请按照以下步骤操作（请在 5 分钟内完成）：")
        print("1. 在浏览器中打开以下 URL：")
        print(post_login)
        print("2. 登录你的 Nintendo 账号")
        print('3. 右键点击"Select this account"按钮')
        print("4. 复制链接地址")
        print("5. 将复制的链接粘贴到下方（输入'skip'跳过）：")
        
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                use_account_url = input("")
                if use_account_url.lower() == "skip":
                    return "skip"
                    
                parsed_query = parse_qs(urlparse(use_account_url).query)
                session_token_codes = parsed_query.get("session_token_code", [])
                if not session_token_codes:
                    print("URL格式不正确，请确保包含'session_token_code'参数")
                    attempt += 1
                    if attempt < max_attempts:
                        print(f"请重新输入 (尝试 {attempt}/{max_attempts}):")
                    continue
                    
                session_token_code = session_token_codes[0]
                result = self.get_session_token(session_token_code, auth_code_verifier)
                if result is None:
                    print("\nToken 可能已过期，请重新运行程序获取新的链接")
                    return None
                return result
            except KeyboardInterrupt:
                print("\n程序已终止")
                sys.exit(1)
            except Exception as e:
                logger.error(f"处理用户输入时出错: {str(e)}")
                print(f"发生错误: {str(e)}")
                attempt += 1
                if attempt < max_attempts:
                    print(f"请重新输入 (尝试 {attempt}/{max_attempts}):")
                else:
                    print("已达到最大尝试次数，程序将退出")
                    return None
 
    def get_session_token(self, session_token_code, auth_code_verifier):
        '''获取会话令牌'''
        app_head = {
            'User-Agent':      self.ua,
            'Accept-Language': 'en-US',
            'Accept':          'application/json',
            'Content-Type':    'application/x-www-form-urlencoded',
            'Host':            'accounts.nintendo.com',
            'Connection':      'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }

        body = {
            'client_id':                   self.client_id,
            'session_token_code':          session_token_code,
            'session_token_code_verifier': auth_code_verifier.replace(b"=", b"").decode('utf-8')
        }

        url = 'https://accounts.nintendo.com/connect/1.0.0/api/session_token'

        try:
            r = self.session.post(url, headers=app_head, data=body, timeout=self.timeout)
            
            if r.status_code != 200:
                logger.error(f"获取会话令牌失败，状态码: {r.status_code}")
                return None
                
            response_data = json.loads(r.text)
            if 'session_token' not in response_data:
                logger.error("响应中未找到 session_token")
                return None
                
            self.session_token = response_data['session_token']
            return self.session_token
        except Exception as e:
            logger.error(f"获取会话令牌失败: {str(e)}")
            return None
 
    def get_access_token(self):
        '''获取访问令牌'''
        if not hasattr(self, 'session_token') or not self.session_token:
            logger.error("缺少会话令牌，无法获取访问令牌")
            return None
            
        body = {
            "client_id": self.client_id,
            "session_token": self.session_token,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer-session-token"
        }
        
        url = 'https://accounts.nintendo.com/connect/1.0.0/api/token'
 
        try:
            r = self.session.post(
                url, 
                headers={'Content-Type': 'application/json'}, 
                data=json.dumps(body),
                timeout=self.timeout
            )
            
            if r.status_code != 200:
                logger.error(f"获取访问令牌失败，状态码: {r.status_code}")
                return None
                
            self.access_token = json.loads(r.text)
            # 保存新获取的 token
            self.save_tokens()
            
            return self.access_token
        except Exception as e:
            logger.error(f"获取访问令牌失败: {str(e)}")
            return None
 
    def get_history(self, archive_json=False):
        '''获取游戏历史记录'''
        if not hasattr(self, 'access_token') or not self.access_token:
            logger.error("缺少访问令牌，无法获取游戏历史记录")
            return None
            
        url = 'https://news-api.entry.nintendo.co.jp/api/v1.1/users/me/play_histories'
        header = {
            'Authorization': f"{self.access_token['token_type']} {self.access_token['access_token']}",
            'User-Agent': self.ua,
        }
        try:
            r = self.session.get(url, headers=header, timeout=self.timeout)
            
            if r.status_code == 200:
                try:
                    data = r.json()
                    if archive_json:
                        save_dir = PROJECT_ROOT / "history_data"
                        save_dir.mkdir(parents=True, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filepath = save_dir / f"history_{timestamp}.json"
                        with filepath.open("w", encoding="utf-8") as file_handle:
                            json.dump(data, file_handle, ensure_ascii=False, indent=2)
                        print(f"历史记录已保存到: {filepath}")
                    
                    # 保存数据到数据库
                    if save_to_database(data):
                        print("数据已成功保存到数据库")
                    else:
                        print("保存数据到数据库失败")
                    
                    # 打印简要信息（优先使用中文名称）
                    games = get_game_list_with_cn_names()
                    if games:
                        history_count = len(games)
                        print(f"\n共找到 {history_count} 条游戏记录")
                        for _, display_name, days in games[:5]:  # 显示前5条记录
                            print(f"- {display_name}: {days} 天")
                except Exception as e:
                    logger.error(f"保存历史记录失败: {str(e)}")
                    print(f"保存历史记录失败: {str(e)}")
            elif r.status_code == 401:  # token 失效
                logger.warning("访问令牌已失效，需要重新登录")
                print("token 已失效，需要重新登录")
                # 删除失效的 token
                if self.token_file.exists():
                    try:
                        self.token_file.unlink()
                    except OSError as e:
                        logger.error(f"删除 token 文件失败: {str(e)}")
                return None
            else:
                logger.error(f"获取历史记录失败，状态码: {r.status_code}")
                print(f"获取历史记录失败，状态码: {r.status_code}")
                return None
                
            return r
        except Exception as e:
            logger.error(f"获取历史记录失败: {str(e)}")
            print(f"请求失败: {str(e)}")
            return None
 
def main(argv=None):
    parser = argparse.ArgumentParser(description="收集 Nintendo Switch 游玩记录")
    parser.add_argument(
        "--archive-json",
        action="store_true",
        help="将 API 原始响应额外保存到 history_data/（默认仅写入数据库）",
    )
    args = parser.parse_args(argv)
    try:
        print("Nintendo Switch 游戏记录追踪工具")
        
        # 初始化数据库
        init_database(DB_FILE)
            
        ns = NintendoSession()
        
        # 修改逻辑：先检查是否有session_token（长期有效），无论access_token是否有效
        if hasattr(ns, 'session_token') and ns.session_token:
            # 有session_token但access_token无效，直接刷新access_token
            if not ns.check_tokens_valid():
                print("访问令牌已过期，正在刷新...")
                access_token = ns.get_access_token()
                if not access_token:
                    print("刷新访问令牌失败")
                    return 1
        else:
            # 没有session_token，需要完整登录流程
            session_token = ns.log_in()
            if not session_token:
                print("登录失败")
                return 1
                
            if session_token == "skip":
                print("已跳过登录")
                return 0
                
            access_token = ns.get_access_token()
            if not access_token:
                print("获取访问令牌失败")
                return 1
        
        # 获取游戏历史
        if hasattr(ns, 'access_token') and ns.access_token:
            r = ns.get_history(archive_json=args.archive_json)
            if not r:
                print("获取游戏历史记录失败")
                return 1
        else:
            print("缺少访问令牌，无法获取游戏历史记录")
            return 1
            
        print("程序执行完成")
        return 0
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
        return 130
    except Exception as e:
        logger.error(f"程序发生未捕获的异常: {str(e)}", exc_info=True)
        print(f"程序发生错误: {str(e)}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
