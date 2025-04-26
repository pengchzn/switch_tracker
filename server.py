import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, render_template, request
from calendar import monthrange

app = Flask(__name__)

# 数据库配置
DB_FILE = 'switch_tracker.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>')
def static_files(path):
    """提供静态文件"""
    return send_from_directory('.', path)

@app.route('/api/monthly_playtime')
def monthly_playtime():
    """获取每月游玩时间统计数据"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 查询每日游玩记录，按月份汇总
        cursor.execute('''
        SELECT 
            strftime('%Y-%m', played_date) as month,
            SUM(played_minutes) as total_minutes
        FROM daily_play
        GROUP BY month
        ORDER BY month
        ''')
        
        monthly_data = {}
        for row in cursor.fetchall():
            month, minutes = row
            monthly_data[month] = minutes
        
        # 移除对当前月份的估算处理，只使用实际数据
        
        conn.close()
        return jsonify(monthly_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games')
def get_games():
    conn = get_db_connection()
    
    # 获取游戏列表，优先使用中文名称
    cursor = conn.execute('''
        SELECT 
            g.title_id, 
            CASE 
                WHEN g.chinese_name IS NOT NULL AND g.chinese_name != '' 
                THEN g.chinese_name 
                ELSE g.title_name 
            END AS display_name,
            g.title_name AS original_name,
            g.image_url,
            g.device_type,
            MAX(h.total_played_days) AS total_played_days,
            MAX(h.total_played_minutes) AS total_played_minutes,
            MAX(h.last_played_at) AS last_played_at,
            MIN(h.first_played_at) AS first_played_at
        FROM games g
        JOIN game_history h ON g.title_id = h.title_id
        GROUP BY g.title_id
        ORDER BY total_played_minutes DESC
    ''')
    
    games = []
    for row in cursor:
        games.append({
            'title_id': row['title_id'],
            'name': row['display_name'],
            'original_name': row['original_name'],
            'image_url': row['image_url'],
            'device_type': row['device_type'],
            'total_played_days': row['total_played_days'],
            'total_played_minutes': row['total_played_minutes'],
            'last_played_at': row['last_played_at'],
            'first_played_at': row['first_played_at']
        })
    
    conn.close()
    return jsonify(games)

@app.route('/api/game/<title_id>/daily')
def get_game_daily(title_id):
    conn = get_db_connection()
    
    # 获取游戏信息，优先使用中文名称
    cursor = conn.execute('''
        SELECT 
            title_id, 
            CASE 
                WHEN chinese_name IS NOT NULL AND chinese_name != '' 
                THEN chinese_name 
                ELSE title_name 
            END AS display_name,
            image_url
        FROM games
        WHERE title_id = ?
    ''', (title_id,))
    
    game = cursor.fetchone()
    if not game:
        conn.close()
        return jsonify({'error': 'Game not found'}), 404
    
    # 获取每日游玩数据
    cursor = conn.execute('''
        SELECT played_date, played_minutes
        FROM daily_play
        WHERE title_id = ?
        ORDER BY played_date ASC
    ''', (title_id,))
    
    daily_data = []
    for row in cursor:
        daily_data.append({
            'date': row['played_date'],
            'minutes': row['played_minutes']
        })
    
    result = {
        'title_id': game['title_id'],
        'name': game['display_name'],
        'image_url': game['image_url'],
        'daily_data': daily_data
    }
    
    conn.close()
    return jsonify(result)

@app.route('/api/history')
def get_history():
    conn = get_db_connection()
    
    # 获取所有历史记录的日期（从每日游玩记录中）
    cursor = conn.execute('''
        SELECT DISTINCT played_date
        FROM daily_play
        ORDER BY played_date DESC
    ''')
    
    dates = [row['played_date'] for row in cursor]
    
    history = []
    for date in dates:
        # 获取当天玩的游戏，优先使用中文名称
        cursor = conn.execute('''
            SELECT 
                d.title_id,
                CASE 
                    WHEN g.chinese_name IS NOT NULL AND g.chinese_name != '' 
                    THEN g.chinese_name 
                    ELSE g.title_name 
                END AS display_name,
                g.image_url,
                d.played_minutes
            FROM daily_play d
            JOIN games g ON d.title_id = g.title_id
            WHERE d.played_date = ?
            ORDER BY d.played_minutes DESC
        ''', (date,))
        
        games = []
        for row in cursor:
            games.append({
                'title_id': row['title_id'],
                'name': row['display_name'],
                'image_url': row['image_url'],
                'minutes': row['played_minutes']
            })
        
        if games:  # 只添加有游戏记录的日期
            history.append({
                'date': date,
                'games': games
            })
    
    conn.close()
    return jsonify(history)

@app.route('/api/recent_activities')
def recent_activities():
    """获取最近几天的游玩记录"""
    try:
        conn = get_db_connection()
        
        # 获取最近7天有记录的日期
        cursor = conn.execute('''
        SELECT DISTINCT played_date
        FROM daily_play
        ORDER BY played_date DESC
        LIMIT 7
        ''')
        
        dates = [row['played_date'] for row in cursor]
        
        recent_activities = []
        for date in dates:
            # 获取该日期的游玩记录，优先使用中文名称，并使用GROUP BY title_id去重
            cursor = conn.execute('''
            SELECT 
                d.title_id,
                CASE 
                    WHEN g.chinese_name IS NOT NULL AND g.chinese_name != '' 
                    THEN g.chinese_name 
                    ELSE g.title_name 
                END AS display_name,
                g.image_url,
                SUM(d.played_minutes) as total_minutes
            FROM daily_play d
            JOIN games g ON d.title_id = g.title_id
            WHERE d.played_date = ?
            GROUP BY d.title_id
            ORDER BY total_minutes DESC
            ''', (date,))
            
            daily_games = []
            for row in cursor:
                daily_games.append({
                    'titleId': row['title_id'],
                    'titleName': row['display_name'],
                    'imageUrl': row['image_url'],
                    'totalPlayedMinutes': row['total_minutes']
                })
            
            if daily_games:  # 只添加有游戏记录的日期
                recent_activities.append({
                    'playedDate': date,
                    'dailyPlayHistories': daily_games
                })
        
        conn.close()
        
        # 调试返回数据结构
        print(f"recent_activities API返回 {len(recent_activities)} 条记录")
        
        return jsonify({'recentPlayHistories': recent_activities})
    except Exception as e:
        print(f"recent_activities API错误: {str(e)}")
        return jsonify({'error': str(e), 'recentPlayHistories': []}), 500

@app.route('/test')
def test_page():
    """测试页面，显示原始数据"""
    try:
        conn = get_db_connection()
        
        # 获取游戏列表
        cursor = conn.execute('''
            SELECT 
                title_id, title_name, chinese_name, image_url
            FROM games
            LIMIT 20
        ''')
        
        games = [dict(row) for row in cursor]
        
        # 获取每日游玩记录
        cursor = conn.execute('''
            SELECT played_date, COUNT(*) as game_count, SUM(played_minutes) as total_minutes
            FROM daily_play
            GROUP BY played_date
            ORDER BY played_date DESC
            LIMIT 10
        ''')
        
        daily_stats = [dict(row) for row in cursor]
        
        conn.close()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>数据测试</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2 { color: #333; }
                table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                img { max-width: 100px; max-height: 100px; }
            </style>
        </head>
        <body>
            <h1>数据测试页面</h1>
            
            <h2>游戏数据 (""" + str(len(games)) + """ 条记录)</h2>
            <table>
                <tr>
                    <th>ID</th>
                    <th>原始名称</th>
                    <th>中文名称</th>
                    <th>图片</th>
                </tr>
        """
        
        for g in games:
            html += f"""<tr>
                <td>{g['title_id']}</td>
                <td>{g['title_name']}</td>
                <td>{g['chinese_name'] or '无'}</td>
                <td><img src="{g['image_url']}" onerror="this.src='https://via.placeholder.com/100x100?text=No+Image'"></td>
            </tr>"""
            
        html += """
            </table>
            
            <h2>每日统计 (""" + str(len(daily_stats)) + """ 条记录)</h2>
            <table>
                <tr>
                    <th>日期</th>
                    <th>游戏数量</th>
                    <th>总时长 (分钟)</th>
                </tr>
        """
        
        for d in daily_stats:
            html += f"""<tr>
                <td>{d['played_date']}</td>
                <td>{d['game_count']}</td>
                <td>{d['total_minutes']}</td>
            </tr>"""
            
        html += """
            </table>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        return f"<h1>错误</h1><p>{str(e)}</p>"

if __name__ == '__main__':
    # 确保数据库文件存在
    if not os.path.exists(DB_FILE):
        print(f"数据库文件 {DB_FILE} 不存在，请先运行 get_switch_data.py 获取数据")
    else:
        # 确保模板目录存在
        if not os.path.exists('templates'):
            os.makedirs('templates')
        
        # 创建或更新index.html
        with open('templates/index.html', 'w') as f:
            f.write(open('index.html').read())
        
        app.run(host='0.0.0.0', port=8000, debug=True) 