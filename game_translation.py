import csv
import sqlite3
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("switch_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("game_translation")

# 数据库配置
DB_FILE = 'switch_tracker.db'
TRANSLATION_CSV = 'game_translations.csv'

def init_translation_table():
    """初始化游戏翻译表结构"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 检查游戏翻译表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_translations'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # 检查updated_at列是否存在
            cursor.execute("PRAGMA table_info(game_translations)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'updated_at' not in columns:
                # 添加缺少的updated_at列
                cursor.execute('ALTER TABLE game_translations ADD COLUMN updated_at TEXT')
                logger.info("已向game_translations表添加updated_at字段")
        else:
            # 创建游戏翻译表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_translations (
                title_id TEXT PRIMARY KEY,
                japanese_name TEXT NOT NULL,
                chinese_name TEXT NOT NULL,
                updated_at TEXT
            )
            ''')
            logger.info("已创建game_translations表")
        
        # 添加中文名称字段到games表（如果不存在）
        cursor.execute("PRAGMA table_info(games)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'chinese_name' not in columns:
            cursor.execute('ALTER TABLE games ADD COLUMN chinese_name TEXT')
            logger.info("已向games表添加chinese_name字段")
        
        conn.commit()
        conn.close()
        logger.info("游戏翻译表初始化成功")
        return True
    except Exception as e:
        logger.error(f"初始化游戏翻译表失败: {str(e)}")
        return False

def create_empty_translation_csv():
    """如果不存在，创建一个空的翻译CSV文件"""
    if not os.path.exists(TRANSLATION_CSV):
        try:
            with open(TRANSLATION_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['title_id', 'japanese_name', 'chinese_name'])
            logger.info(f"已创建空的翻译文件: {TRANSLATION_CSV}")
            return True
        except Exception as e:
            logger.error(f"创建翻译文件失败: {str(e)}")
            return False
    return True

def export_untranslated_games():
    """导出未翻译的游戏到CSV文件"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 查找所有未翻译的游戏
        cursor.execute('''
        SELECT g.title_id, g.title_name 
        FROM games g
        LEFT JOIN game_translations t ON g.title_id = t.title_id
        WHERE t.title_id IS NULL
        ORDER BY g.title_name
        ''')
        
        untranslated_games = cursor.fetchall()
        conn.close()
        
        if not untranslated_games:
            print("没有找到需要翻译的游戏")
            return True
            
        # 备份现有的翻译文件
        if os.path.exists(TRANSLATION_CSV):
            backup_file = f"{TRANSLATION_CSV}.bak"
            try:
                os.replace(TRANSLATION_CSV, backup_file)
                logger.info(f"已将现有翻译文件备份为: {backup_file}")
            except Exception as e:
                logger.warning(f"备份翻译文件失败: {str(e)}")
        
        # 读取现有翻译
        existing_translations = {}
        if os.path.exists(f"{TRANSLATION_CSV}.bak"):
            try:
                with open(f"{TRANSLATION_CSV}.bak", 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # 跳过标题行
                    for row in reader:
                        if len(row) >= 3 and row[0] and row[2]:
                            existing_translations[row[0]] = (row[1], row[2])
            except Exception as e:
                logger.warning(f"读取现有翻译失败: {str(e)}")
        
        # 创建新的翻译文件
        with open(TRANSLATION_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['title_id', 'japanese_name', 'chinese_name'])
            
            # 先写入现有的翻译
            for title_id, (jp_name, cn_name) in existing_translations.items():
                writer.writerow([title_id, jp_name, cn_name])
            
            # 添加未翻译的游戏
            untranslated_count = 0
            for title_id, jp_name in untranslated_games:
                if title_id not in existing_translations:
                    writer.writerow([title_id, jp_name, ''])
                    untranslated_count += 1
        
        print(f"已导出 {untranslated_count} 个未翻译的游戏到 {TRANSLATION_CSV}")
        print(f"请编辑该文件添加中文翻译，然后运行 'python game_translation.py import' 导入翻译")
        return True
    except Exception as e:
        logger.error(f"导出未翻译游戏失败: {str(e)}")
        print(f"导出未翻译游戏失败: {str(e)}")
        return False

def import_translations_from_csv():
    """从CSV文件导入游戏翻译"""
    if not os.path.exists(TRANSLATION_CSV):
        print(f"翻译文件 {TRANSLATION_CSV} 不存在")
        return False
        
    try:
        # 读取CSV文件
        translations = []
        with open(TRANSLATION_CSV, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过标题行
            for row in reader:
                if len(row) >= 3 and row[0] and row[2]:  # 确保有title_id和chinese_name
                    translations.append((row[0], row[1], row[2]))
        
        if not translations:
            print("没有找到有效的翻译记录")
            return False
            
        # 导入到数据库
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 当前时间
        import datetime
        now = datetime.datetime.now().isoformat()
        
        # 检查updated_at列是否存在
        cursor.execute("PRAGMA table_info(game_translations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'updated_at' in columns:
            # 如果有updated_at列，使用完整的SQL
            for title_id, jp_name, cn_name in translations:
                cursor.execute('''
                INSERT OR REPLACE INTO game_translations 
                (title_id, japanese_name, chinese_name, updated_at)
                VALUES (?, ?, ?, ?)
                ''', (title_id, jp_name, cn_name, now))
        else:
            # 如果没有updated_at列，跳过该字段
            for title_id, jp_name, cn_name in translations:
                cursor.execute('''
                INSERT OR REPLACE INTO game_translations 
                (title_id, japanese_name, chinese_name)
                VALUES (?, ?, ?)
                ''', (title_id, jp_name, cn_name))
        
        # 同时更新games表中的chinese_name
        for title_id, _, cn_name in translations:
            cursor.execute('''
            UPDATE games SET chinese_name = ? WHERE title_id = ?
            ''', (cn_name, title_id))
        
        conn.commit()
        conn.close()
        
        print(f"成功导入 {len(translations)} 条翻译记录")
        return True
    except Exception as e:
        logger.error(f"导入翻译失败: {str(e)}")
        print(f"导入翻译失败: {str(e)}")
        return False

def apply_translations():
    """将已有翻译应用到games表"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 更新games表中的chinese_name
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
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"已将 {updated_count} 个游戏的中文名称应用到数据库")
        return True
    except Exception as e:
        logger.error(f"应用翻译失败: {str(e)}")
        print(f"应用翻译失败: {str(e)}")
        return False

def main():
    import sys
    
    # 初始化表结构
    if not init_translation_table():
        print("初始化翻译表失败，程序将退出")
        return
    
    # 确保CSV文件存在
    create_empty_translation_csv()
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "export":
            export_untranslated_games()
        elif command == "import":
            import_translations_from_csv()
        elif command == "apply":
            apply_translations()
        else:
            print("未知命令。可用命令: export, import, apply")
    else:
        # 默认操作：导出未翻译的游戏
        export_untranslated_games()
        
if __name__ == "__main__":
    main() 