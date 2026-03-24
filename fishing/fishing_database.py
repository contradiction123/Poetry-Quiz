"""
钓鱼游戏数据记录模块
使用SQLite存储游戏记录，为AI学习做准备
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import os


class FishingDatabase:
    """钓鱼游戏数据库类"""
    
    def __init__(self, db_path: str = "fishing_records.db"):
        """
        初始化数据库
        参数:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建游戏记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fishing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                rod_level INTEGER,
                hook_level INTEGER,
                game_state TEXT,  -- JSON格式的游戏状态
                decision TEXT,    -- JSON格式的决策信息
                result TEXT,      -- JSON格式的结果信息
                score INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON fishing_records(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_score ON fishing_records(score)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_record(
        self,
        rod_level: int,
        hook_level: int,
        game_state: Dict,
        decision: Dict,
        result: Dict,
        score: int = 0
    ) -> int:
        """
        添加游戏记录
        参数:
            rod_level: 鱼竿等级
            hook_level: 鱼钩等级
            game_state: 游戏状态字典
            decision: 决策信息字典
            result: 结果信息字典
            score: 获得的分数
        返回: 记录ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute('''
            INSERT INTO fishing_records 
            (timestamp, rod_level, hook_level, game_state, decision, result, score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            rod_level,
            hook_level,
            json.dumps(game_state, ensure_ascii=False),
            json.dumps(decision, ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
            score
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def get_recent_records(self, limit: int = 100) -> List[Dict]:
        """
        获取最近的记录
        参数:
            limit: 返回记录数
        返回: 记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM fishing_records
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        records = []
        for row in rows:
            record = dict(row)
            # 解析JSON字段
            if record['game_state']:
                record['game_state'] = json.loads(record['game_state'])
            if record['decision']:
                record['decision'] = json.loads(record['decision'])
            if record['result']:
                record['result'] = json.loads(record['result'])
            records.append(record)
        
        return records
    
    def get_statistics(self) -> Dict:
        """
        获取统计信息
        返回: 统计字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总记录数
        cursor.execute('SELECT COUNT(*) FROM fishing_records')
        total_records = cursor.fetchone()[0]
        
        # 总分数
        cursor.execute('SELECT SUM(score) FROM fishing_records')
        total_score = cursor.fetchone()[0] or 0
        
        # 平均分数
        cursor.execute('SELECT AVG(score) FROM fishing_records')
        avg_score = cursor.fetchone()[0] or 0
        
        # 成功次数（result.success = true）
        cursor.execute('''
            SELECT COUNT(*) FROM fishing_records
            WHERE result LIKE '%"success": true%'
        ''')
        success_count = cursor.fetchone()[0]
        
        # 成功率
        success_rate = (success_count / total_records * 100) if total_records > 0 else 0
        
        conn.close()
        
        return {
            'total_records': total_records,
            'total_score': total_score,
            'avg_score': round(avg_score, 2),
            'success_count': success_count,
            'success_rate': round(success_rate, 2)
        }
    
    def export_to_csv(self, output_path: str = "fishing_records.csv"):
        """
        导出记录为CSV文件
        参数:
            output_path: 输出文件路径
        """
        import csv
        
        records = self.get_recent_records(limit=10000)  # 导出所有记录
        
        if not records:
            return
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入表头
            writer.writerow([
                'ID', 'Timestamp', 'Rod Level', 'Hook Level',
                'Score', 'Success', 'Time Taken', 'Fish Caught'
            ])
            
            # 写入数据
            for record in records:
                result = record.get('result', {})
                writer.writerow([
                    record['id'],
                    record['timestamp'],
                    record['rod_level'],
                    record['hook_level'],
                    record['score'],
                    result.get('success', False),
                    result.get('time_taken', 0),
                    result.get('fish_caught', 0)
                ])
    
    def clear_all_records(self):
        """清空所有记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM fishing_records')
        conn.commit()
        conn.close()
