"""
数据库模块
使用SQLite记录答题历史和统计
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "answer_history.db", timeout: float = 0.2, busy_timeout_ms: int = 200):
        """
        初始化数据库
        参数:
            db_path: 数据库文件路径
            timeout: sqlite 连接等待锁超时（秒）。默认调小，避免卡住整轮流程
            busy_timeout_ms: sqlite busy_timeout（毫秒），与 timeout 配合使用
        """
        self.db_path = db_path
        self.timeout = timeout
        self.busy_timeout_ms = busy_timeout_ms
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        # 尽量提升并发可用性（读写并发），同时减少等待锁的时间
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)};")
        except Exception:
            pass
        return conn

    def _update_statistics_cursor(self, cursor: sqlite3.Cursor, is_correct: int):
        """
        在同一个事务中更新统计（避免 add_answer_record 内部再开新连接导致自锁）
        """
        # 更新总数
        cursor.execute("UPDATE statistics SET total_questions = total_questions + 1")

        # 更新正确/错误数
        if is_correct:
            cursor.execute("UPDATE statistics SET correct_answers = correct_answers + 1")
        else:
            cursor.execute("UPDATE statistics SET wrong_answers = wrong_answers + 1")

        # 计算准确率
        cursor.execute("""
            UPDATE statistics 
            SET accuracy_rate = CAST(correct_answers AS REAL) / total_questions * 100,
                last_updated = CURRENT_TIMESTAMP
            WHERE total_questions > 0
        """)
    
    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 创建答题历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_answer TEXT,
                ai_answer TEXT,
                is_correct INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_questions INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                wrong_answers INTEGER DEFAULT 0,
                accuracy_rate REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 初始化统计记录
        cursor.execute("SELECT COUNT(*) FROM statistics")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO statistics (total_questions, correct_answers, wrong_answers, accuracy_rate)
                VALUES (0, 0, 0, 0.0)
            """)
        
        conn.commit()
        conn.close()
    
    def add_answer_record(self, question: str, options: Dict[str, str], 
                         ai_answer: str, correct_answer: Optional[str] = None) -> int:
        """
        添加答题记录
        参数:
            question: 题目
            options: 选项字典 {'A': '选项A', ...}
            ai_answer: AI返回的答案
            correct_answer: 正确答案（如果知道）
        返回:
            int: 记录ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        is_correct = 1 if (correct_answer and ai_answer == correct_answer) else 0
        
        cursor.execute("""
            INSERT INTO answer_history 
            (question, option_a, option_b, option_c, option_d, ai_answer, correct_answer, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            question,
            options.get('A', ''),
            options.get('B', ''),
            options.get('C', ''),
            options.get('D', ''),
            ai_answer,
            correct_answer or '',
            is_correct
        ))
        
        record_id = cursor.lastrowid
        
        # 更新统计（同事务，避免自锁）
        self._update_statistics_cursor(cursor, is_correct)
        
        conn.commit()
        conn.close()
        
        return record_id
    
    def update_statistics(self, is_correct: int):
        """
        更新统计数据
        参数:
            is_correct: 1表示正确，0表示错误
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        self._update_statistics_cursor(cursor, is_correct)
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """
        获取统计数据
        返回:
            dict: 统计数据
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT total_questions, correct_answers, wrong_answers, accuracy_rate, last_updated
            FROM statistics
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'total_questions': row[0],
                'correct_answers': row[1],
                'wrong_answers': row[2],
                'accuracy_rate': round(row[3], 2) if row[3] else 0.0,
                'last_updated': row[4]
            }
        else:
            return {
                'total_questions': 0,
                'correct_answers': 0,
                'wrong_answers': 0,
                'accuracy_rate': 0.0,
                'last_updated': None
            }
    
    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的答题历史
        参数:
            limit: 返回记录数
        返回:
            list: 历史记录列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, question, ai_answer, correct_answer, is_correct, created_at
            FROM answer_history
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        history = []
        for row in rows:
            history.append({
                'id': row[0],
                'question': row[1],
                'ai_answer': row[2],
                'correct_answer': row[3],
                'is_correct': bool(row[4]),
                'created_at': row[5]
            })
        
        return history
    
    def search_question(self, question: str) -> Optional[Dict]:
        """
        搜索题目（用于查找历史答案）
        参数:
            question: 题目文字
        返回:
            dict: 历史记录，如果找到
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT question, option_a, option_b, option_c, option_d, ai_answer, is_correct
            FROM answer_history
            WHERE question LIKE ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (f'%{question}%',))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'question': row[0],
                'options': {
                    'A': row[1],
                    'B': row[2],
                    'C': row[3],
                    'D': row[4]
                },
                'ai_answer': row[5],
                'is_correct': bool(row[6])
            }
        
        return None
    
    def clear_history(self):
        """清空答题历史"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM answer_history")
        cursor.execute("""
            UPDATE statistics 
            SET total_questions = 0,
                correct_answers = 0,
                wrong_answers = 0,
                accuracy_rate = 0.0
        """)
        
        conn.commit()
        conn.close()


# 测试代码
if __name__ == "__main__":
    db = Database("test.db")
    
    # 测试添加记录
    options = {
        'A': '玉碗盛来琥珀光',
        'B': '夜泊秦淮近酒家',
        'C': '碧天如水夜云轻',
        'D': '依旧烟笼十里堤'
    }
    
    record_id = db.add_answer_record(
        question="兰陵美酒郁金香",
        options=options,
        ai_answer="A",
        correct_answer="A"
    )
    print(f"添加记录成功，ID: {record_id}")
    
    # 测试获取统计
    stats = db.get_statistics()
    print(f"统计数据: {stats}")
    
    # 测试获取历史
    history = db.get_recent_history(5)
    print(f"最近历史: {history}")
    
    # 清理测试数据库
    os.remove("test.db")
