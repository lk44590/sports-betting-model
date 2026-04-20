"""
Paper Trading Module
Automatic virtual bet tracking and performance monitoring
"""

from .auto_trader import auto_trader, PaperTradingSettings
from .models import PaperBet, PaperBankroll

__all__ = ['auto_trader', 'PaperTradingSettings', 'PaperBet', 'PaperBankroll']
