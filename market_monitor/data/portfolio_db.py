"""
SQLite 历史数据库 —— 持仓快照、选股推荐、信号历史 持久化模块。

三张核心表：
    1. portfolio_snapshots  — 每次持仓分析的完整快照
    2. selection_recommendations — 选股推荐记录 + 7天后表现追踪
    3. signal_history — 每只ETF的信号时间序列

使用示例：
    from market_monitor.data.portfolio_db import PortfolioDB
    
    db = PortfolioDB()
    db.save_snapshot("2026-06-28", results)
    last_week = db.get_last_week("2026-06-28")
    db.track_recommendation("2026-06-28", recommendations)
    stats = db.get_tracking_stats()
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio_history.db")


class PortfolioDB:
    """持仓历史数据库"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_schema()
    
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_schema(self):
        """初始化三张表 schema"""
        with self._connect() as conn:
            conn.executescript("""
                -- 表1: 持仓快照
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT NOT NULL,          -- YYYY-MM-DD
                    etf_code    TEXT NOT NULL,           -- ETF代码
                    etf_name    TEXT,                    -- ETF名称
                    signal      TEXT,                    -- BUY/HOLD_BULL/HOLD_NEUTRAL/HOLD_BEAR/SELL
                    position    TEXT,                    -- 多头排列/空头排列/纠缠整理
                    kdj_j       REAL,                    -- KDJ_J值
                    kdj_k       REAL,
                    kdj_d       REAL,
                    score       REAL,                    -- pattern_score
                    price       REAL,                    -- 收盘价
                    profit_pct  REAL,                    -- 盈亏百分比
                    market_value REAL,                   -- 市值
                    rsi14       REAL,
                    trend_diff_pct REAL,                -- 趋势差值%
                    created_at  TEXT DEFAULT (datetime('now','localtime'))
                );
                
                -- 索引加速查询
                CREATE INDEX IF NOT EXISTS idx_snap_date ON portfolio_snapshots(date);
                CREATE INDEX IF NOT EXISTS idx_snap_code ON portfolio_snapshots(etf_code);
                CREATE INDEX IF NOT EXISTS idx_snap_date_code ON portfolio_snapshots(date, etf_code);
                
                -- 表2: 选股推荐追踪
                CREATE TABLE IF NOT EXISTS selection_recommendations (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    rec_date        TEXT NOT NULL,       -- 推荐日期
                    etf_code        TEXT NOT NULL,        -- ETF代码
                    etf_name        TEXT,                 -- ETF名称
                    signal          TEXT,                 -- 推荐时的信号
                    score           REAL,                 -- 综合评分
                    kdj_j           REAL,                 -- 推荐时KDJ_J
                    etf_type        TEXT,                 -- ETF类型
                    price_at_rec    REAL,                 -- 推荐时价格
                    price_at_check  REAL,                 -- 7天后检查价格
                    actual_return_7d REAL,               -- 7日实际收益%
                    hit_status      TEXT,                 -- hit(涨)/miss(跌)/pending
                    checked_date    TEXT,                 -- 检查日期
                    created_at      TEXT DEFAULT (datetime('now','localtime'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_rec_date ON selection_recommendations(rec_date);
                CREATE INDEX IF NOT EXISTS idx_rec_hit ON selection_recommendations(hit_status);
                
                -- 表3: 信号历史（逐日信号变化）
                CREATE TABLE IF NOT EXISTS signal_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    etf_code    TEXT NOT NULL,
                    date        TEXT NOT NULL,           -- YYYY-MM-DD
                    signal      TEXT,
                    position    TEXT,
                    score       REAL,
                    kdj_j       REAL,
                    prev_signal TEXT,                    -- 前一天信号（用于对比）
                    prev_score  REAL,                    -- 前一天评分
                    score_change REAL,                   -- 评分变化
                    created_at  TEXT DEFAULT (datetime('now','localtime')),
                    UNIQUE(etf_code, date)
                );
                
                CREATE INDEX IF NOT EXISTS idx_sig_code ON signal_history(etf_code);
                CREATE INDEX IF NOT EXISTS idx_sig_date ON signal_history(date);
            """)
    
    # ═══ 表1: 持仓快照 ═══════════════════════════════════════════════════════
    
    def save_snapshot(self, date: str, results: List[Dict]) -> int:
        """保存一次持仓分析快照。
        
        Args:
            date: 日期 "YYYY-MM-DD"
            results: analyze_etf 输出的结果列表
        
        Returns:
            写入行数
        """
        if not results:
            return 0
        
        with self._connect() as conn:
            # 先删除当天已有数据（幂等）
            conn.execute("DELETE FROM portfolio_snapshots WHERE date = ?", (date,))
            
            rows = []
            for r in results:
                rows.append((
                    date,
                    r.get('etf_code', ''),
                    r.get('etf_name', r.get('index_name', '')),
                    r.get('signal', ''),
                    r.get('position', ''),
                    r.get('kdj_j', 0),
                    r.get('kdj_k', 0),
                    r.get('kdj_d', 0),
                    r.get('pattern_score', 0),
                    r.get('close', 0),
                    r.get('profit_pct', 0),
                    r.get('market_value', 0),
                    r.get('rsi14', 50),
                    r.get('trend_diff_pct', r.get('short_pct_long', 0)),
                ))
            
            conn.executemany(
                """INSERT INTO portfolio_snapshots 
                   (date, etf_code, etf_name, signal, position, kdj_j, kdj_k, kdj_d,
                    score, price, profit_pct, market_value, rsi14, trend_diff_pct)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
            conn.commit()
            return len(rows)
    
    def query_snapshots(self, date: str = None, etf_code: str = None, 
                        start: str = None, end: str = None) -> List[Dict]:
        """查询快照数据。
        
        Args:
            date: 精确日期
            etf_code: 过滤ETF代码
            start/end: 日期范围
        """
        with self._connect() as conn:
            sql = "SELECT * FROM portfolio_snapshots WHERE 1=1"
            params = []
            
            if date:
                sql += " AND date = ?"
                params.append(date)
            if etf_code:
                sql += " AND etf_code = ?"
                params.append(etf_code)
            if start:
                sql += " AND date >= ?"
                params.append(start)
            if end:
                sql += " AND date <= ?"
                params.append(end)
            
            sql += " ORDER BY date DESC, etf_code"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    
    def get_last_week(self, date: str) -> List[Dict]:
        """获取最近一次快照（早于指定日期最近的一个交易日）。
        
        用于"本周vs上周"对比。
        """
        with self._connect() as conn:
            row = conn.execute(
                """SELECT DISTINCT date FROM portfolio_snapshots 
                   WHERE date < ? ORDER BY date DESC LIMIT 1""",
                (date,)
            ).fetchone()
            
            if not row:
                return []
            
            last_date = row[0]
            return self.query_snapshots(date=last_date)
    
    def get_signal_changes(self, current_date: str) -> List[Dict]:
        """获取与上期相比的信号变化。
        
        Returns:
            [{etf_code, etf_name, prev_signal, curr_signal, prev_score, curr_score, score_change}, ...]
        """
        last_snap = self.get_last_week(current_date)
        curr_snap = self.query_snapshots(date=current_date)
        
        if not last_snap:
            return []
        
        last_map = {r['etf_code']: r for r in last_snap}
        changes = []
        
        for curr in curr_snap:
            code = curr['etf_code']
            prev = last_map.get(code)
            if prev and prev.get('signal') != curr.get('signal'):
                changes.append({
                    'etf_code': code,
                    'etf_name': curr.get('etf_name', ''),
                    'prev_signal': prev.get('signal', ''),
                    'curr_signal': curr.get('signal', ''),
                    'prev_score': prev.get('score', 0),
                    'curr_score': curr.get('score', 0),
                    'score_change': (curr.get('score', 0) or 0) - (prev.get('score', 0) or 0),
                })
        
        return changes
    
    # ═══ 表2: 选股推荐追踪 ═════════════════════════════════════════════════
    
    def track_recommendation(self, date: str, recommendations: List[Dict]) -> int:
        """记录选股推荐。
        
        Args:
            date: 推荐日期
            recommendations: [{etf_code, etf_name, signal, score, kdj_j, etf_type, price}, ...]
        """
        if not recommendations:
            return 0
        
        with self._connect() as conn:
            rows = []
            for r in recommendations:
                rows.append((
                    date,
                    r.get('code', r.get('etf_code', '')),
                    r.get('name', r.get('etf_name', '')),
                    r.get('signal', ''),
                    r.get('total_score', r.get('score', 0)),
                    r.get('kdj_j', 0),
                    r.get('etf_type', ''),
                    r.get('price', 0),
                ))
            
            conn.executemany(
                """INSERT INTO selection_recommendations 
                   (rec_date, etf_code, etf_name, signal, score, kdj_j, etf_type, price_at_rec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
            conn.commit()
            return len(rows)
    
    def check_performance(self, date: str) -> Dict:
        """检查7天前推荐的标的实际表现。
        
        Args:
            date: 检查日期（当天）
        
        Returns:
            {total, hits, misses, hit_rate, avg_return, details: [...]}
        """
        from datetime import datetime as dt
        target_date = (dt.strptime(date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        
        with self._connect() as conn:
            recs = conn.execute(
                """SELECT * FROM selection_recommendations 
                   WHERE rec_date = ? AND hit_status IS NULL""",
                (target_date,)
            ).fetchall()
        
        if not recs:
            return {"total": 0, "hits": 0, "misses": 0, "hit_rate": 0, "avg_return": 0, "details": []}
        
        total = len(recs)
        hits = 0
        details = []
        total_return = 0.0
        
        for r in recs:
            status = "hit" if (r['actual_return_7d'] or 0) > 0 else "miss"
            if status == "hit":
                hits += 1
            total_return += (r['actual_return_7d'] or 0)
            details.append(dict(r))
        
        return {
            "total": total,
            "hits": hits,
            "misses": total - hits,
            "hit_rate": hits / total * 100 if total else 0,
            "avg_return": total_return / total if total else 0,
            "details": details,
        }
    
    def get_tracking_stats(self) -> Dict:
        """获取累计选股追踪统计（累计命中率/胜率/平均收益）。"""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN hit_status = 'hit' THEN 1 ELSE 0 END) as hits,
                    AVG(actual_return_7d) as avg_return
                 FROM selection_recommendations 
                 WHERE hit_status IS NOT NULL"""
            ).fetchone()
        
        total = row['total'] or 0
        hits = row['hits'] or 0
        
        return {
            "total_checked": total,
            "hits": hits,
            "misses": total - hits,
            "hit_rate": hits / total * 100 if total else 0,
            "avg_return_7d": round(row['avg_return'] or 0, 2),
        }
    
    def update_tracking(self, etf_code: str, rec_date: str, 
                        current_price: float, checked_date: str) -> bool:
        """更新追踪记录：填写7天后实际价格和涨跌。
        
        Args:
            etf_code: ETF代码
            rec_date: 推荐日期
            current_price: 当前价格
            checked_date: 检查日期
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT price_at_rec FROM selection_recommendations WHERE etf_code = ? AND rec_date = ?",
                (etf_code, rec_date)
            ).fetchone()
            
            if not row or not row['price_at_rec']:
                return False
            
            price_at_rec = row['price_at_rec']
            actual_return = (current_price - price_at_rec) / price_at_rec * 100 if price_at_rec else 0
            hit_status = "hit" if actual_return > 0 else "miss"
            
            conn.execute(
                """UPDATE selection_recommendations 
                   SET price_at_check = ?, actual_return_7d = ?, hit_status = ?, checked_date = ?
                   WHERE etf_code = ? AND rec_date = ?""",
                (current_price, actual_return, hit_status, checked_date, etf_code, rec_date)
            )
            conn.commit()
            return True
    
    # ═══ 表3: 信号历史 ═══════════════════════════════════════════════════════
    
    def save_signal_history(self, date: str, results: List[Dict]) -> int:
        """保存信号历史（记录每天信号变化）。"""
        if not results:
            return 0
        
        with self._connect() as conn:
            rows = []
            for r in results:
                code = r.get('etf_code', '')
                
                # 查找前一次信号
                prev = conn.execute(
                    "SELECT signal, score FROM signal_history WHERE etf_code = ? ORDER BY date DESC LIMIT 1",
                    (code,)
                ).fetchone()
                
                prev_signal = prev['signal'] if prev else None
                prev_score = prev['score'] if prev else None
                curr_score = r.get('pattern_score', 0)
                score_change = (curr_score or 0) - (prev_score or 0) if prev_score is not None else 0
                
                rows.append((
                    code,
                    date,
                    r.get('signal', ''),
                    r.get('position', ''),
                    curr_score,
                    r.get('kdj_j', 0),
                    prev_signal,
                    prev_score,
                    score_change,
                ))
            
            conn.executemany(
                """INSERT OR REPLACE INTO signal_history 
                   (etf_code, date, signal, position, score, kdj_j, prev_signal, prev_score, score_change)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
            conn.commit()
            return len(rows)
    
    def get_signal_timeline(self, etf_code: str, days: int = 30) -> List[Dict]:
        """查询指定ETF的信号时间线。"""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT date, signal, position, score, kdj_j, score_change 
                   FROM signal_history 
                   WHERE etf_code = ? 
                   ORDER BY date DESC LIMIT ?""",
                (etf_code, days)
            ).fetchall()
            return [dict(r) for r in rows]


# 便捷单例
_db_instance: Optional[PortfolioDB] = None


def get_db() -> PortfolioDB:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PortfolioDB()
    return _db_instance
