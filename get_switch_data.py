import requests
import json
import base64
import hashlib
import re
import sys
import os
import sqlite3
from datetime import datetime, timedelta
import time
import logging

# 配置日志 - 仅保留关键日志
logging.basicConfig(
    level=logging.WARNING,  # 改为WARNING级别，减少日志量
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("switch_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("switch_tracker")

# 数据库配置
DB_FILE = 'switch_tracker.db'

def init_database():
    """初始化数据库表结构"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 创建游戏表 - 存储游戏基本信息
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            title_id TEXT PRIMARY KEY,
            title_name TEXT NOT NULL,
            image_url TEXT,
            device_type TEXT,
            chinese_name TEXT
        )
        ''')
        
        # 创建游戏历史记录表 - 存储每次获取的游戏总时长
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_id TEXT NOT NULL,
            first_played_at TEXT,
            last_played_at TEXT,
            total_played_days INTEGER,
            total_played_minutes INTEGER,
            collected_at TEXT NOT NULL,
            FOREIGN KEY (title_id) REFERENCES games (title_id)
        )
        ''')
        
        # 创建每日游玩记录表 - 存储每天的游玩记录
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_play (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_id TEXT NOT NULL,
            played_date TEXT NOT NULL,
            played_minutes INTEGER NOT NULL,
            collected_at TEXT NOT NULL,
            FOREIGN KEY (title_id) REFERENCES games (title_id)
        )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"初始化数据库失败: {str(e)}")
        return False

def save_to_database(data):
    """将游戏数据保存到数据库中"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 当前时间作为数据收集时间
        collected_at = datetime.now().isoformat()
        
        # 保存游戏基本信息
        for game in data.get('playHistories', []):
            # 插入或更新游戏记录
            cursor.execute('''
            INSERT OR REPLACE INTO games (title_id, title_name, image_url, device_type)
            VALUES (?, ?, ?, ?)
            ''', (
                game.get('titleId'), 
                game.get('titleName'), 
                game.get('imageUrl'),
                game.get('deviceType')
            ))
            
            # 保存游戏历史记录
            cursor.execute('''
            INSERT INTO game_history (
                title_id, first_played_at, last_played_at, 
                total_played_days, total_played_minutes, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                game.get('titleId'),
                game.get('firstPlayedAt'),
                game.get('lastPlayedAt'),
                game.get('totalPlayedDays'),
                game.get('totalPlayedMinutes'),
                collected_at
            ))
        
        # 保存每日游玩记录
        for day_record in data.get('recentPlayHistories', []):
            played_date = day_record.get('playedDate')
            
            for game in day_record.get('dailyPlayHistories', []):
                # 只保存有游玩时间的记录
                if game.get('totalPlayedMinutes', 0) > 0:
                    cursor.execute('''
                    INSERT INTO daily_play (title_id, played_date, played_minutes, collected_at)
                    VALUES (?, ?, ?, ?)
                    ''', (
                        game.get('titleId'),
                        played_date,
                        game.get('totalPlayedMinutes'),
                        collected_at
                    ))
        
        conn.commit()
        
        # 更新现有游戏的中文名称（如果有翻译）
        cursor.execute('''
        UPDATE games 
        SET chinese_name = (
            SELECT t.chinese_name 
            FROM game_translations t 
            WHERE t.title_id = games.title_id
        )
        WHERE EXISTS (
            SELECT 1 
            FROM game_translations t 
            WHERE t.title_id = games.title_id
        )
        ''')
        
        # 检查是否有未翻译的游戏
        cursor.execute('''
        SELECT COUNT(*) 
        FROM games 
        WHERE chinese_name IS NULL OR chinese_name = ''
        ''')
        untranslated_count = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        logger.info(f"数据已成功保存到数据库")
        
        # 打印信息并检查未翻译的游戏
        if untranslated_count > 0:
            print(f"发现 {untranslated_count} 个未翻译的游戏，可以运行 'python game_translation.py' 导出并翻译")
        
        return True
    except Exception as e:
        logger.error(f"保存数据到数据库失败: {str(e)}")
        return False

def get_game_list_with_cn_names():
    """获取游戏列表，优先使用中文名称"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT title_id, 
               CASE WHEN chinese_name IS NOT NULL AND chinese_name != '' 
                    THEN chinese_name 
                    ELSE title_name 
               END AS display_name,
               total_played_days
        FROM games
        JOIN (
            SELECT title_id, MAX(total_played_days) as total_played_days
            FROM game_history
            GROUP BY title_id
        ) h ON games.title_id = h.title_id
        ORDER BY total_played_days DESC
        LIMIT 10
        ''')
        
        games = cursor.fetchall()
        conn.close()
        
        return games
    except Exception as e:
        logger.error(f"获取游戏列表失败: {str(e)}")
        return []

class nsession:
 
    def __init__(self, client_id='5c38e31cd085304b') -> None:
        self.session = requests.Session()
        self.client_id = client_id
        self.ua = 'com.nintendo.znej/1.13.0 (Android/7.1.2)'
        self.config_dir = 'config'
        self.token_file = os.path.join(self.config_dir, 'tokens.json')
        self.timeout = 30  # 请求超时时间（秒）
        self.load_tokens()
 
    def load_tokens(self):
        """从配置文件加载已保存的 token"""
        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir)
            except OSError as e:
                logger.error(f"创建配置目录失败: {str(e)}")
                return False
            
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
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
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)
                
            with open(self.token_file, 'w') as f:
                json.dump(tokens, f)
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
                    
                session_token_code_match = re.search(r'session_token_code=([^&]+)', use_account_url)
                if not session_token_code_match:
                    print("URL格式不正确，请确保包含'session_token_code'参数")
                    attempt += 1
                    if attempt < max_attempts:
                        print(f"请重新输入 (尝试 {attempt}/{max_attempts}):")
                    continue
                    
                session_token_code = session_token_code_match.group(1)
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
                logger.error(f"响应中未找到 session_token")
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
 
    def get_history(self):
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
                # 创建保存目录
                save_dir = 'history_data'
                try:
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    
                    # 生成文件名（使用时间戳）
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f'history_{timestamp}.json'
                    filepath = os.path.join(save_dir, filename)
                    
                    # 获取响应数据
                    data = r.json()
                    
                    # 保存数据到JSON文件
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
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
                        for i, (title_id, display_name, days) in enumerate(games[:5]):  # 显示前5条记录
                            print(f"- {display_name}: {days} 天")
                except Exception as e:
                    logger.error(f"保存历史记录失败: {str(e)}")
                    print(f"保存历史记录失败: {str(e)}")
            elif r.status_code == 401:  # token 失效
                logger.warning("访问令牌已失效，需要重新登录")
                print("token 已失效，需要重新登录")
                # 删除失效的 token
                if os.path.exists(self.token_file):
                    try:
                        os.remove(self.token_file)
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
 
def main():
    try:
        print("Nintendo Switch 游戏记录追踪工具")
        
        # 初始化数据库
        if not init_database():
            print("初始化数据库失败，程序将退出")
            return
            
        ns = nsession()
        
        # 修改逻辑：先检查是否有session_token（长期有效），无论access_token是否有效
        if hasattr(ns, 'session_token') and ns.session_token:
            # 有session_token但access_token无效，直接刷新access_token
            if not ns.check_tokens_valid():
                print("访问令牌已过期，正在刷新...")
                access_token = ns.get_access_token()
                if not access_token:
                    print("刷新访问令牌失败")
                    return
        else:
            # 没有session_token，需要完整登录流程
            session_token = ns.log_in()
            if not session_token:
                print("登录失败")
                return
                
            if session_token == "skip":
                print("已跳过登录")
                return
                
            access_token = ns.get_access_token()
            if not access_token:
                print("获取访问令牌失败")
                return
        
        # 获取游戏历史
        if hasattr(ns, 'access_token') and ns.access_token:
            r = ns.get_history()
            if not r:
                print("获取游戏历史记录失败")
        else:
            print("缺少访问令牌，无法获取游戏历史记录")
            
        print("程序执行完成")
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
    except Exception as e:
        logger.error(f"程序发生未捕获的异常: {str(e)}", exc_info=True)
        print(f"程序发生错误: {str(e)}")

if __name__ == "__main__":
    main()
