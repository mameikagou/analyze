"""
多因子组合器 —— 把多个 score 因子加权组合成一个综合分。

对应现有 scoring.py:score_funds() 的 Z-Score 标准化 + 加权逻辑，
但改为面板级运算（一次性处理所有基金、所有日期）。

为什么用 Z-Score 标准化？
不同因子的量纲不同（动量是百分比，夏普是无量纲比率，回撤是负数），
不能直接相加。Z-Score 把每个因子转成"相对同日期其他基金的偏离程度"，
消除量纲差异，让加权有意义。

与现有代码的关系：
- scoring.py:_compute_z_scores() 是"列表级"Z-Score（对一组数值）
- CompositeFactor 是"面板级"Z-Score（对 DataFrame 的每行），语义一致但维度升级
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base import BaseFactor, FactorOutput


class CompositeFactor(BaseFactor):
    """
    把多个 score 因子加权组合成一个综合分。

    组合流程：
    1. 对每个因子分别计算输出（得到各自的分数矩阵）
    2. 对每个因子的分数矩阵做横截面 Z-Score 标准化（按日期分组，每行独立标准化）
    3. 按权重加权求和

    关键约束：
    - 所有输入因子必须是 kind="score"，signal/weight 因子不能直接用 + 组合
    - Z-Score 计算时 std=0（该日所有基金分数相同）→ Z-Score 全 0，不贡献分数
    """

    def __init__(
        self,
        factors: list[BaseFactor],
        weights: Optional[list[float]] = None,
        name: str = "composite",
    ) -> None:
        """
        初始化复合因子。

        Args:
            factors: 子因子列表，每个必须是 kind="score" 的 BaseFactor 实例
            weights: 权重列表，长度必须和 factors 一致。默认等权。
            name: 复合因子名称

        Raises:
            AssertionError: 如果有因子的 kind 不是 "score"
            ValueError: 如果 weights 长度和 factors 不一致
        """
        # 防御：因子列表不能为空（否则 weights = [1.0/0] 会触发 ZeroDivisionError）
        if not factors:
            raise ValueError("factors 不能为空列表")

        self.factors = factors
        self.weights = weights or [1.0 / len(factors)] * len(factors)
        self.name = name

        if len(self.factors) != len(self.weights):
            raise ValueError(
                f"因子数量 ({len(self.factors)}) 和权重数量 ({len(self.weights)}) 不一致"
            )

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        """
        计算复合分数矩阵。

        Args:
            nav_panel: 宽表 DataFrame，index=date，columns=fund_code，values=净值
            **context: 额外上下文，会传给每个子因子的 compute()

        Returns:
            FactorOutput，values 为浮点矩阵（Z-Score 加权求和），kind="score"
        """
        combined: Optional[pd.DataFrame] = None

        for factor, weight in zip(self.factors, self.weights):
            output = factor.compute(nav_panel, **context)

            # 防御：只有 score 因子可以组合
            if output.kind != "score":
                raise ValueError(
                    f"CompositeFactor 只能组合 kind='score' 的因子，"
                    f"但 {factor.name} 的 kind='{output.kind}'"
                )

            scores = output.values

            # 横截面 Z-Score 标准化（按日期分组，每行独立标准化）
            # axis=1: 对每行（每个日期）计算 mean/std，跨基金（columns）
            mean = scores.mean(axis=1)
            std = scores.std(axis=1, ddof=1)

            # std == 0 的日期 → Z-Score 全 0（该日因子不贡献分数，避免除以零产生 inf）
            # 步骤：
            # 1. scores.sub(mean, axis=0): 每个值减去该行均值
            # 2. .div(std.replace(0, np.nan), axis=0): 除以该行标准差，std=0 的位置变成 NaN
            # 3. .fillna(0): NaN 位置（std=0）填 0
            z = scores.sub(mean, axis=0).div(std.replace(0, np.nan), axis=0).fillna(0)

            if combined is None:
                combined = z * weight
            else:
                combined = combined + z * weight

        # combined 不可能为 None，因为 __init__ 会检查 factors 非空
        # 但类型检查器不知道，加个断言
        assert combined is not None

        return FactorOutput(
            values=combined,
            kind="score",
            name=self.name,
            description=f"{len(self.factors)} 因子加权组合（权重: {self.weights}）",
        )
