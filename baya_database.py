# ═══════════════════════════════════════════════════════════════════
#                  BAYA EMPIRE - نظام قاعدة البيانات
#                      Professional Trading Database
# ═══════════════════════════════════════════════════════════════════

import sqlite3
import pandas as pd
from datetime import datetime, date
import logging
import threading

class BayaDatabase:
    """نظام قاعدة البيانات الاحترافي للصفقات"""
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, db_name="baya_empire.db"):
        """Singleton Pattern - نسخة واحدة فقط"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_name)
        return cls._instance
    
    def __init__(self, db_name="baya_empire.db"):
        if hasattr(self, '_initialized'):
            return
        self.db_name = db_name
        self.logger = logging.getLogger("BayaDB")
        logging.basicConfig(level=logging.INFO)
        self.setup_database()
        self._initialized = True
    
    def get_connection(self):
        """الاتصال بقاعدة البيانات"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def setup_database(self):
        """إنشاء الجداول"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # جدول الصفقات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    amount REAL NOT NULL,
                    profit REAL DEFAULT 0,
                    status TEXT DEFAULT 'OPEN',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    close_timestamp DATETIME,
                    strategy TEXT,
                    notes TEXT
                )
            ''')
            
            # جدول الرصيد اليومي
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_balance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_usdt REAL NOT NULL,
                    date DATE UNIQUE NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
        self.logger.info("✅ تم إنشاء قاعدة البيانات")
    
    def log_trade(self, symbol, side, price, amount, strategy=None, notes=None):
        """تسجيل صفقة جديدة"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO trades (symbol, side, entry_price, amount, strategy, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (symbol.upper(), side.upper(), price, amount, strategy, notes, datetime.now()))
        self.logger.info(f"📝 صفقة مسجلة: {symbol} {side} @ ${price}")
    
    def close_trade(self, trade_id, exit_price, profit=None, notes=None):
        """إغلاق صفقة"""
        with self.get_connection() as conn:
            # جلب بيانات الصفقة
            cursor = conn.cursor()
            cursor.execute("SELECT side, entry_price, amount FROM trades WHERE id = ?", (trade_id,))
            trade = cursor.fetchone()
            
            if not trade:
                return False
            
            # حساب الربح
            if profit is None:
                if trade['side'] == 'LONG':
                    profit = (exit_price - trade['entry_price']) * trade['amount']
                else:
                    profit = (trade['entry_price'] - exit_price) * trade['amount']
            
            # تحديث الصفقة
            conn.execute('''
                UPDATE trades 
                SET exit_price = ?, profit = ?, status = 'CLOSED', 
                    close_timestamp = ?, notes = ?
                WHERE id = ?
            ''', (exit_price, profit, datetime.now(), notes, trade_id))
            
        self.logger.info(f"✅ تم إغلاق صفقة #{trade_id} | الربح: ${profit:.2f}")
        return True
    
    def get_trade_history(self, symbol=None, status=None):
        """جلب تاريخ الصفقات"""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY timestamp DESC"
        
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    
    def get_open_trades(self):
        """جلب الصفقات المفتوحة"""
        with self.get_connection() as conn:
            return pd.read_sql_query(
                "SELECT * FROM trades WHERE status = 'OPEN' ORDER BY timestamp DESC",
                conn
            )
    
    def get_performance_stats(self):
        """حساب إحصائيات الأداء"""
        df = self.get_trade_history(status='CLOSED')
        
        if df.empty:
            return {
                "win_rate": 0, "total_profit": 0, "trade_count": 0,
                "winners": 0, "losers": 0, "sharpe_ratio": 0,
                "max_drawdown": 0, "profit_factor": 0
            }
        
        wins = df[df['profit'] > 0]
        losses = df[df['profit'] < 0]
        
        total = len(df)
        winners = len(wins)
        losers = len(losses)
        
        win_rate = (winners / total * 100) if total > 0 else 0
        total_profit = df['profit'].sum()
        
        # Sharpe Ratio
        if len(df) > 1:
            mean = df['profit'].mean()
            std = df['profit'].std()
            sharpe = mean / std if std > 0 else 0
        else:
            sharpe = 0
        
        # Max Drawdown
        cumsum = df['profit'].cumsum()
        running_max = cumsum.cummax()
        drawdown = cumsum - running_max
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        # Profit Factor
        gross_profit = wins['profit'].sum() if not wins.empty else 0
        gross_loss = abs(losses['profit'].sum()) if not losses.empty else 0
        pf = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return {
            "win_rate": round(win_rate, 2),
            "total_profit": round(total_profit, 2),
            "trade_count": total,
            "winners": winners,
            "losers": losers,
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "profit_factor": round(pf, 2)
        }
    
    def get_daily_pnl(self):
        """الأرباح اليومية"""
        df = self.get_trade_history(status='CLOSED')
        if df.empty:
            return pd.DataFrame()
        
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        return df.groupby('date')['profit'].sum().reset_index()
    
    def log_daily_balance(self, total_usdt):
        """تسجيل الرصيد اليومي"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO daily_balance (total_usdt, date)
                VALUES (?, ?)
            ''', (total_usdt, date.today()))
    
    def get_balance_history(self, days=30):
        """جلب تاريخ الرصيد"""
        with self.get_connection() as conn:
            return pd.read_sql_query(
                "SELECT * FROM daily_balance ORDER BY date DESC LIMIT ?",
                conn, params=[days]
            )
    
    def create_backup(self):
        """إنشاء نسخة احتياطية"""
        import shutil
        from pathlib import Path
        
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{timestamp}.db"
        
        shutil.copy2(self.db_name, backup_path)
        self.logger.info(f"💾 تم إنشاء نسخة احتياطية: {backup_path}")
        return str(backup_path)

# ═══════════════════════════════════════════════════════════════════
#                         TEST
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    db = BayaDatabase.get_instance("test.db")
    
    # إضافة صفقات تجريبية
    t1 = db.log_trade("BTCUSDT", "LONG", 45000, 0.1, "Breakout")
    t2 = db.log_trade("ETHUSDT", "SHORT", 3000, 2, "Mean Reversion")
    
    # إغلاق الصفقات
    db.close_trade(t1, 46000)  # ربح
    db.close_trade(t2, 2900)   # ربح
    
    # عرض الإحصائيات
    stats = db.get_performance_stats()
    print("\n📊 إحصائيات الأداء:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
