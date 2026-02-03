#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远期点插值模块
根据起息日和到期日从远期点报表中插值计算远期点数。
"""

from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional, Tuple


def parse_date_ddmmyyyy(s: str) -> Optional[date]:
    """解析日期字符串，支持 YYYY/MM/DD 或 DD/MM/YYYY 格式"""
    if not s:
        return None
    
    parts = s.split('/')
    if len(parts) != 3:
        return None
    
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


class PointsInterpolator:
    """远期点插值器"""
    
    def __init__(self, csv_path: str):
        self.points_data: Dict[str, List[Dict]] = {}
        self.load_points_csv(csv_path)
    
    def load_points_csv(self, csv_path: str):
        """加载远期点报表"""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_pair = None
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 分割行
                parts = line.split(',')
                
                # 如果第一行只有一个字段，可能是货币对
                if len(parts) == 1:
                    first_part = parts[0].strip()
                    # 货币对格式：EURUSD 或 EUR/USD
                    if first_part.isalpha() and len(first_part) >= 5:
                        current_pair = first_part
                        if current_pair not in self.points_data:
                            self.points_data[current_pair] = []
                    elif '/' in first_part:
                        current_pair = first_part
                        if current_pair not in self.points_data:
                            self.points_data[current_pair] = []
                    continue
                
                # 如果第一个字段是 "Tenor"，跳过（这是列头行）
                first_part = parts[0].strip()
                if first_part == 'Tenor':
                    continue
                
                # 数据行
                if current_pair and len(parts) >= 4:
                    try:
                        settlement_date = parse_date_ddmmyyyy(parts[1].strip())
                        bid_pts = Decimal(parts[2].strip())
                        ask_pts = Decimal(parts[3].strip())
                        
                        if settlement_date:
                            mid_pts = (bid_pts + ask_pts) / 2
                            self.points_data[current_pair].append({
                                'settlement_date': settlement_date,
                                'bid_points': bid_pts,
                                'ask_points': ask_pts,
                                'mid_points': mid_pts
                            })
                    except (ValueError, IndexError):
                        continue
        except FileNotFoundError:
            pass
    
    def interpolate(self, pair: str, value_date: date, mat_date: date, 
                    current_date: Optional[date] = None) -> Optional[Decimal]:
        """
        插值计算远期点数
        
        Args:
            pair: 货币对
            value_date: 起息日
            mat_date: 到期日
            current_date: 当前日期，默认为今天
            
        Returns:
            插值后的点数，失败返回 None
        """
        if pair not in self.points_data:
            return None
        
        if not mat_date:
            return None
        
        # 使用今天作为当前日期（如果未指定）
        if current_date is None:
            current_date = date.today()
        
        # 如果当前日期已经超过起息日，使用当前日期计算剩余天数
        # 如果当前日期还在起息日之前，使用起息日计算
        if current_date < value_date:
            calc_date = value_date
        else:
            calc_date = current_date
        
        if mat_date <= calc_date:
            return None
        
        # 计算目标天数：从计算日期到 Mat Date 的天数差
        target_days = (mat_date - calc_date).days
        
        quotes = self.points_data[pair]
        if not quotes:
            return None
        
        # 构建序列：(天数差, mid_points)
        # 只考虑 settlement_date 晚于 calc_date 的报价
        series = []
        for q in quotes:
            q_days = (q['settlement_date'] - calc_date).days
            if q_days <= 0:
                continue  # 跳过 settlement_date <= calc_date 的报价
            series.append((q_days, q['mid_points']))
        
        if not series:
            return None
        
        # 按天数升序排列
        series.sort(key=lambda x: x[0])
        
        # 边界处理
        if target_days <= series[0][0]:
            return series[0][1]
        
        if target_days >= series[-1][0]:
            return series[-1][1]
        
        # 线性插值
        for (d0, p0), (d1, p1) in zip(series, series[1:]):
            if d0 <= target_days <= d1:
                if d1 == d0:
                    return p0
                ratio = Decimal(target_days - d0) / Decimal(d1 - d0)
                return p0 + (p1 - p0) * ratio
        
        return None


def points_divisor_by_pair(pair: str) -> int:
    """
    根据货币对返回除数
    
    Args:
        pair: 货币对，如 'JPY/CNY', 'USD/CNY', 'EUR/USD'
        
    Returns:
        除数，JPY 基准为 1000000，其他为 10000
    """
    if not pair or '/' not in pair:
        return 10000
    
    base = pair.split('/')[0].upper().strip()
    
    # JPY 基准的货币对使用 1000000
    if base == 'JPY':
        return 1000000
    
    return 10000


def normalize_pair_for_points(pair: str) -> str:
    """
    标准化货币对格式，用于远期点报表查找
    EUR/USD -> EURUSD
    """
    return pair.replace('/', '').upper()


# 便捷函数
def create_interpolator(csv_path: str) -> PointsInterpolator:
    """创建远期点插值器"""
    return PointsInterpolator(csv_path)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python points_interpolator.py <远期点报表.csv>")
        sys.exit(1)
    
    interpolator = PointsInterpolator(sys.argv[1])
    print(f"加载了 {len(interpolator.points_data)} 个货币对的数据")
    
    for pair, quotes in interpolator.points_data.items():
        print(f"\n{pair}:")
        for q in quotes[:5]:
            print(f"  {q['settlement_date']}: 点数={q['mid_points']}")
