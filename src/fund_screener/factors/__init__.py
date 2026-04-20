"""
因子层包 —— 统一导出所有因子类。

用法：
    from fund_screener.factors import (
        BaseFactor, FactorOutput,
        MACrossFactor, MomentumFactor,
        SharpeFactor, MaxDrawdownFactor,
        CompositeFactor,
    )
"""

from .base import BaseFactor, FactorOutput
from .composite import CompositeFactor
from .quant import MaxDrawdownFactor, MomentumFactor, SharpeFactor
from .technical import MACrossFactor

__all__ = [
    "BaseFactor",
    "FactorOutput",
    "MACrossFactor",
    "MomentumFactor",
    "SharpeFactor",
    "MaxDrawdownFactor",
    "CompositeFactor",
]
