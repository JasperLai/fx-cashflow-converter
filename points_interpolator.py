#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
远期点插值模块
根据起息日和到期日从远期点报表中插值计算远期点数。
"""

import csv
from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# 期限到天数的映射
TENOR_DAYS = {
    'ON': 1,      # Overnight
    'TN': 2,      # Tomorrow Next
    'SP': 0,      # Spot (即期，通常是交易日后2天)
    'SN': 3,      # Spot Next
    '1W': 7,      # 1 Week
    '2W': 14,     # 2 Weeks
    '3W': 21,     # 3 Weeks
    '1M': 30,     # 1 Month
    '2M': 60,     # 2 Months
    '3M': 90,     # 3 Months
    '4M': 120,    # 4 Months
    '5M': 150,    # 5 Months
    '6M': 180,    # 6 Months
    '9M': 270,    # 9 Months
    '15M': 450,   # 15 Months
    '18M': 540,   # 18 Months
    '1Y': 365,    # 1 Year
    '2Y': 730,    # 2 Years
    '3Y': 1095,   # 3 Years
    '4Y': 1460,   # 4 Years
    '5Y': 1825,   # 5 Years
}


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
                
                # 如果第一行只有一个字段，可能是货币对或列头
                if len(parts) == 1:
                    first_part = parts[0].strip()
                    # 货币对格式：EURUSD 或 EUR/USD
                    if first_part.isalpha() and len(first_part) >= 5:
                        # 纯字母的货币对（如 EURUSD, USDJPY）
                        current_pair = first_part
                        if current_pair not in self.points_data:
                            self.points_data[current_pair] = []
                    elif '/' in first_part:
                        # 带斜杠的货币对（如 EUR/USD）
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
                    tenor = parts[0].strip()
                    try:
                        bid_pts = Decimal(parts[2].strip())
                        avg_pts = (bid_pts + Decimal(parts[3].strip())) / 2
                        days = TENOR_DAYS.get(tenor, 0)
                        
                        self.points_data[current_pair].append({
                            'tenor': tenor,
                            'days': days,
                            'bid_points': bid_pts,
                            'avg_points': avg_pts
                        })
                    except (ValueError, IndexError):
                        continue
        except FileNotFoundError:
            pass
    
    def get_business_days(self, start_date: date, end_date: date) -> int:
        """计算两个日期之间的营业日天数（排除周末）"""
        days = 0
        current = start_date
        while current < end_date:
            if current.weekday() < 5:  # 0-4 是周一到周五
                days += 1
            current += timedelta(days=1)
        return days
    
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
        
        # 计算从计算日期到到期日的营业日天数
        target_days = self.get_business_days(calc_date, mat_date)
        
        points_list = self.points_data[pair]
        if not points_list:
            return None
        
        # 按天数排序
        points_list.sort(key=lambda x: x['days'])
        
        # 边界检查
        if target_days <= points_list[0]['days']:
            return points_list[0]['avg_points']
        
        if target_days >= points_list[-1]['days']:
            return points_list[-1]['avg_points']
        
        # 线性插值
        for i in range(len(points_list) - 1):
            p1 = points_list[i]
            p2 = points_list[i+1]
            
            if p1['days'] <= target_days <= p2['days']:
                # 线性插值
                ratio = Decimal(target_days - p1['days']) / Decimal(p2['days'] - p1['days'])
                interpolated = p1['avg_points'] + ratio * (p2['avg_points'] - p1['avg_points'])
                return interpolated
        
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


# 便捷函数
def create_interpolator(csv_path: str) -> PointsInterpolator:
    """创建远期点插值器"""
    return PointsInterpolator(csv_path)


if __name__ == '__main__':
    # 测试代码
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python points_interpolator.py <远期点报表.csv>")
        sys.exit(1)
    
    interpolator = PointsInterpolator(sys.argv[1])
    print(f"加载了 {len(interpolator.points_data)} 个货币对的数据")
    
    for pair, data in interpolator.points_data.items():
        print(f"\n{pair}:")
        for item in data[:5]:  # 只显示前5条
            print(f"  {item['tenor']}: {item['days']} 天, 点数: {item['avg_points']}")
