"""
Paper Trading Models
Database models for virtual bet tracking
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path

Base = declarative_base()

class PaperBet(Base):
    """Virtual/paper bet for tracking model performance"""
    __tablename__ = 'paper_bets'
    
    id = Column(Integer, primary_key=True)
    bet_id = Column(String, unique=True, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    sport = Column(String, nullable=False)
    event = Column(String, nullable=False)
    selection = Column(String, nullable=False)
    bet_type = Column(String, default='moneyline')  # moneyline, spread, total
    odds = Column(Integer, nullable=False)
    stake = Column(Float, nullable=False)
    model_probability = Column(Float, default=0.5)
    ev_pct = Column(Float, default=0.0)
    
    # Result tracking
    result = Column(String, default='pending')  # pending, win, loss, push
    profit = Column(Float, default=0.0)
    settled_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<PaperBet {self.bet_id} {self.selection} ${self.stake} {self.result}>"


class PaperBankroll(Base):
    """Daily bankroll snapshot for paper trading"""
    __tablename__ = 'paper_bankroll'
    
    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, nullable=False)  # YYYY-MM-DD
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=False)
    daily_pnl = Column(Float, default=0.0)
    total_bets = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    pushes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PaperBankroll {self.date} ${self.ending_balance:,.2f}>"


class AutoTradingSettings(Base):
    """Settings for automatic paper trading"""
    __tablename__ = 'auto_trading_settings'
    
    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, default=False)
    starting_bankroll = Column(Float, default=10000.0)
    current_bankroll = Column(Float, default=10000.0)
    kelly_fraction = Column(Float, default=0.2)  # 20% fractional Kelly
    min_ev = Column(Float, default=7.0)  # 7% minimum EV
    max_daily_bets = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AutoTradingSettings enabled={self.enabled} bankroll=${self.current_bankroll:,.2f}>"


# Database setup - LAZY INITIALIZATION to prevent import errors
def init_paper_trading_db(db_path=None):
    """Initialize paper trading database"""
    if db_path is None:
        db_path = Path(__file__).parent.parent.parent / "data" / "paper_trading.db"
    
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        Base.metadata.create_all(engine)
        
        return engine
    except Exception as e:
        print(f"Warning: Could not initialize paper trading database: {e}")
        return None


# Lazy initialization - don't create on import
_engine = None
_Session = None

def get_engine():
    """Get or create database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        _engine = init_paper_trading_db()
    return _engine

def get_session():
    """Get database session"""
    global _Session
    if _Session is None:
        engine = get_engine()
        if engine is None:
            return None
        _Session = sessionmaker(bind=engine)
    return _Session()
