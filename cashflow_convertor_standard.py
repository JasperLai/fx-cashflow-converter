#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外汇交易现金流转换工具
从外汇交易明细数据中提取、计算并汇总现金流，生成可用于风险分析和资金规划的现金流报告。
"""

import csv
import json
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from points_interpolator import PointsInterpolator, points_divisor_by_pair


def parse_decimal(s: str) -> Decimal:
    """解析数值为 Decimal，避免浮点精度问题"""
    if not s:
        return Decimal('0')
    s = s.strip().replace(',', '')
    try:
        return Decimal(s)
    except:
        return Decimal('0')


def normalize_cashflow(ccy: str, amt: Decimal) -> Decimal:
    """标准化现金流金额"""
    if ccy == 'JPY':
        return amt.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return amt


def parse_date_safe(s: str) -> Optional[datetime.date]:
    """安全解析日期，格式: DD/MM/YYYY"""
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s.strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def parse_pair(pair: str) -> Tuple[str, str]:
    """解析货币对"""
    parts = pair.strip().split('/')
    if len(parts) == 2:
        return parts[0].upper().strip(), parts[1].upper().strip()
    return pair.upper().strip(), ''


def is_jpy_base(pair: str) -> bool:
    """判断货币对是否以 JPY 为基础货币"""
    base, _ = parse_pair(pair)
    return base == 'JPY'


def load_filter_config(config_path: Optional[str]) -> Dict:
    """加载过滤配置"""
    if not config_path:
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_trades(input_file: str, ignore_folders: List[str], filter_config: Dict) -> List[Dict]:
    """加载并过滤交易记录"""
    trades = []
    ignore_folders = ignore_folders or filter_config.get('ignore_folders', [])
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = row.get('Folder', '').strip()
            if folder in ignore_folders:
                continue
            trades.append(row)
    
    return trades


def calculate_swap_cashflows(trade: Dict, points_interpolator: Optional[PointsInterpolator]) -> List[Dict]:
    """计算 FX Swap 交易的现金流"""
    cashflows = []
    
    amount1 = parse_decimal(trade.get('Amount1', '0'))
    amount2 = parse_decimal(trade.get('Amount2', '0'))
    pair = trade.get('Security', '')
    value_date = parse_date_safe(trade.get('Value Date', ''))
    mat_date = parse_date_safe(trade.get('Mat. Date', ''))
    rate_price = parse_decimal(trade.get('Rate/Price', '0'))
    
    if amount1 == 0 or not value_date or not mat_date:
        return []
    
    base_ccy, quote_ccy = parse_pair(pair)
    near_rate = abs(amount2 / amount1)
    divisor = points_divisor_by_pair(pair)
    
    # 远端汇率计算
    if points_interpolator and mat_date:
        curve_pts = points_interpolator.interpolate(pair, value_date, mat_date)
        if curve_pts is not None:
            far_rate = near_rate + (curve_pts / divisor)
        else:
            far_rate = near_rate + (rate_price / divisor)
    else:
        far_rate = near_rate + (rate_price / divisor)
    
    # 近端现金流
    cashflows.append({
        'Date': value_date,
        'Currency': base_ccy,
        'Cashflow': normalize_cashflow(base_ccy, amount1),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'FX Swap - Near'
    })
    cashflows.append({
        'Date': value_date,
        'Currency': quote_ccy,
        'Cashflow': normalize_cashflow(quote_ccy, amount2),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'FX Swap - Near'
    })
    
    # 远端现金流
    far_amount2 = amount1 * far_rate
    cashflows.append({
        'Date': mat_date,
        'Currency': base_ccy,
        'Cashflow': normalize_cashflow(base_ccy, -amount1),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'FX Swap - Far'
    })
    cashflows.append({
        'Date': mat_date,
        'Currency': quote_ccy,
        'Cashflow': normalize_cashflow(quote_ccy, far_amount2),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'FX Swap - Far'
    })
    
    return cashflows


def calculate_spot_cashflows(trade: Dict) -> List[Dict]:
    """计算 Spot 交易的现金流"""
    cashflows = []
    
    amount1 = parse_decimal(trade.get('Amount1', '0'))
    amount2 = parse_decimal(trade.get('Amount2', '0'))
    pair = trade.get('Security', '')
    value_date = parse_date_safe(trade.get('Value Date', ''))
    
    if not value_date:
        return []
    
    base_ccy, quote_ccy = parse_pair(pair)
    
    cashflows.append({
        'Date': value_date,
        'Currency': base_ccy,
        'Cashflow': normalize_cashflow(base_ccy, amount1),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'Spot'
    })
    cashflows.append({
        'Date': value_date,
        'Currency': quote_ccy,
        'Cashflow': normalize_cashflow(quote_ccy, amount2),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'Spot'
    })
    
    return cashflows


def calculate_forward_cashflows(trade: Dict) -> List[Dict]:
    """计算 Outright Forward 交易的现金流"""
    cashflows = []
    
    amount1 = parse_decimal(trade.get('Amount1', '0'))
    amount2 = parse_decimal(trade.get('Amount2', '0'))
    pair = trade.get('Security', '')
    mat_date = parse_date_safe(trade.get('Mat. Date', ''))
    
    if not mat_date:
        return []
    
    base_ccy, quote_ccy = parse_pair(pair)
    
    cashflows.append({
        'Date': mat_date,
        'Currency': base_ccy,
        'Cashflow': normalize_cashflow(base_ccy, amount1),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'Outright Forward'
    })
    cashflows.append({
        'Date': mat_date,
        'Currency': quote_ccy,
        'Cashflow': normalize_cashflow(quote_ccy, amount2),
        'TradeId': trade.get('Deal Id', ''),
        'Type': 'Outright Forward'
    })
    
    return cashflows


def calculate_pnl(trade: Dict, points_interpolator: Optional[PointsInterpolator]) -> Dict:
    """计算交易损益"""
    amount1 = parse_decimal(trade.get('Amount1', '0'))
    pair = trade.get('Security', '')
    value_date = parse_date_safe(trade.get('Value Date', ''))
    mat_date = parse_date_safe(trade.get('Mat. Date', ''))
    rate_price = parse_decimal(trade.get('Rate/Price', '0'))
    
    if not value_date or not mat_date or amount1 == 0:
        return {}
    
    _, quote_ccy = parse_pair(pair)
    divisor = points_divisor_by_pair(pair)
    
    pnl = Decimal('0')
    if points_interpolator:
        curve_pts = points_interpolator.interpolate(pair, value_date, mat_date)
        if curve_pts is not None:
            pnl = -amount1 * (curve_pts - rate_price) / divisor
    
    return {
        'Currency': quote_ccy,
        'P&L': pnl
    }


def aggregate_cashflows(cashflows: List[Dict]) -> Dict[Tuple, Decimal]:
    """聚合现金流"""
    aggregated = {}
    for cf in cashflows:
        key = (cf['Date'], cf['Currency'])
        aggregated[key] = aggregated.get(key, Decimal('0')) + cf['Cashflow']
    return aggregated


def generate_csv(aggregated: Dict, output_file: str):
    """生成聚合现金流 CSV"""
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Currency', 'Cashflow'])
        for (date, currency), amount in sorted(aggregated.items()):
            writer.writerow([date.strftime('%Y-%m-%d') if date else '', currency, amount])


def generate_html(cashflows: List[Dict], template_file: str, output_file: str):
    """生成现金流 HTML 报告"""
    today = datetime.date.today()
    future_cashflows = [cf for cf in cashflows if cf['Date'] is None or cf['Date'] >= today]
    future_cashflows.sort(key=lambda x: (x['Date'] or datetime.date.max, x['Currency']))
    
    html = []
    with open(template_file, 'r', encoding='utf-8') as f:
        html = list(f)
    
    # 查找模板中的数据替换位置
    data_start = -1
    data_end = -1
    for i, line in enumerate(html):
        if '<!-- DATA_START -->' in line:
            data_start = i
        elif '<!-- DATA_END -->' in line:
            data_end = i
            break
    
    if data_start >= 0 and data_end > data_start:
        # 生成数据行
        data_rows = []
        for cf in future_cashflows:
            date_str = cf['Date'].strftime('%Y-%m-%d') if cf['Date'] else 'N/A'
            cashflow_str = f"{cf['Cashflow']:,.2f}" if cf['Cashflow'] else '0.00'
            data_rows.append(
                f'            <tr><td>{date_str}</td><td>{cf["Currency"]}</td>'
                f'<td>{cashflow_str}</td><td>{cf["TradeId"]}</td><td>{cf["Type"]}</td></tr>'
            )
        
        html[data_start+1:data_end] = ['\n'.join(data_rows) + '\n']
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(html)


def generate_horizon_summary_html(cashflows: List[Dict], pnl_data: Dict, 
                                  fx_rates: Dict, template_file: str, output_file: str):
    """生成期限汇总 HTML 报告"""
    # 按期限分组现金流
    today = datetime.date.today()
    horizons = {
        'Today': {'cashflows': [], 'start': today, 'end': today},
        'This Week': {'cashflows': [], 'start': today, 'end': today + datetime.timedelta(days=7-today.weekday())},
        'This Month': {'cashflows': [], 'start': today, 'end': today.replace(day=28) + datetime.timedelta(days=4)},
        'Next 3 Months': {'cashflows': [], 'start': today, 'end': today + datetime.timedelta(days=90)},
        'Beyond': {'cashflows': [], 'start': today + datetime.timedelta(days=90), 'end': None}
    }
    
    for cf in cashflows:
        if cf['Date'] is None:
            horizons['Beyond']['cashflows'].append(cf)
        elif cf['Date'] < today:
            horizons['Today']['cashflows'].append(cf)
        elif cf['Date'] < horizons['This Week']['end']:
            horizons['This Week']['cashflows'].append(cf)
        elif cf['Date'] < horizons['This Month']['end']:
            horizons['This Month']['cashflows'].append(cf)
        elif cf['Date'] < horizons['Next 3 Months']['end']:
            horizons['Next 3 Months']['cashflows'].append(cf)
        else:
            horizons['Beyond']['cashflows'].append(cf)
    
    html = []
    with open(template_file, 'r', encoding='utf-8') as f:
        html = list(f)
    
    # 替换 P&L 数据
    for i, line in enumerate(html):
        if '<!-- PNL_DATA -->' in line:
            pnl_lines = []
            for ccy, pnl in pnl_data.items():
                pnl_str = f"{pnl:,.2f}" if pnl else '0.00'
                pnl_lines.append(f'            <tr><td>{ccy}</td><td>{pnl_str}</td></tr>')
            html[i+1:i+2] = ['\n'.join(pnl_lines) + '\n']
            break
    
    # 替换 FX 汇率数据
    for i, line in enumerate(html):
        if '<!-- FX_RATES -->' in line:
            fx_lines = []
            for pair, rate in fx_rates.items():
                fx_lines.append(f'            <tr><td>{pair}</td><td>{rate}</td></tr>')
            html[i+1:i+2] = ['\n'.join(fx_lines) + '\n']
            break
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(html)


def extract_spot_rates(points_file: str) -> Dict:
    """从远期点报表中提取即期汇率"""
    fx_rates = {}
    if not points_file:
        return fx_rates
    
    try:
        with open(points_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_pair = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ',' not in line:
                # 这是货币对标题行
                parts = line.split()
                if parts:
                    current_pair = parts[0].strip()
                continue
            
            parts = line.split(',')
            if len(parts) >= 6 and parts[0].strip() == 'SP':
                pair = current_pair
                bid_outright = parts[4].strip()
                ask_outright = parts[5].strip()
                try:
                    rate = (Decimal(bid_outright) + Decimal(ask_outright)) / 2
                    fx_rates[pair] = str(rate)
                except:
                    pass
    except FileNotFoundError:
        pass
    
    return fx_rates


def main():
    parser = argparse.ArgumentParser(description='外汇交易现金流转换工具')
    parser.add_argument('--input', required=True, help='交易明细 CSV 文件路径')
    parser.add_argument('--template', default='templates/template.html', help='HTML 模板文件路径')
    parser.add_argument('--out_csv', default='cashflows_agg.csv', help='聚合现金流输出文件名')
    parser.add_argument('--out_html', default='cashflows.html', help='现金流 HTML 输出文件名')
    parser.add_argument('--template_summary', default='templates/template_horizon_summary.html', 
                       help='期限汇总 HTML 模板')
    parser.add_argument('--out_html_summary', default='cashflows_horizon_summary.html', 
                       help='期限汇总 HTML 输出文件名')
    parser.add_argument('--out_dir', default='generatedFile', help='输出目录')
    parser.add_argument('--ignore_folders', default='', help='忽略的文件夹列表（逗号分隔）')
    parser.add_argument('--filter_config', default='', help='过滤规则 JSON 文件路径')
    parser.add_argument('--points_csv', default='', help='远期点报表 CSV 文件路径')
    
    args = parser.parse_args()
    
    # 创建输出目录
    Path(args.out_dir).mkdir(exist_ok=True)
    
    # 加载过滤配置
    filter_config = load_filter_config(args.filter_config)
    ignore_folders = [f.strip() for f in args.ignore_folders.split(',') if f.strip()]
    
    # 加载远期点插值器
    points_interpolator = None
    if args.points_csv:
        points_interpolator = PointsInterpolator(args.points_csv)
    
    # 加载交易记录
    trades = load_trades(args.input, ignore_folders, filter_config)
    
    # 计算所有现金流
    all_cashflows = []
    all_pnl = {}
    
    for trade in trades:
        deal_type = trade.get('Type of Deal', '').strip()
        
        if deal_type == 'FX Swap':
            cashflows = calculate_swap_cashflows(trade, points_interpolator)
        elif deal_type == 'Spot':
            cashflows = calculate_spot_cashflows(trade)
        elif deal_type == 'Outright Forward':
            cashflows = calculate_forward_cashflows(trade)
        else:
            cashflows = []
        
        all_cashflows.extend(cashflows)
        
        # 计算 P&L（仅 FX Swap）
        if deal_type == 'FX Swap':
            pnl = calculate_pnl(trade, points_interpolator)
            if pnl:
                ccy = pnl['Currency']
                all_pnl[ccy] = all_pnl.get(ccy, Decimal('0')) + pnl['P&L']
    
    # 聚合现金流
    aggregated = aggregate_cashflows(all_cashflows)
    
    # 生成输出文件
    out_csv_path = Path(args.out_dir) / args.out_csv
    out_html_path = Path(args.out_dir) / args.out_html
    out_html_summary_path = Path(args.out_dir) / args.out_html_summary
    
    generate_csv(aggregated, str(out_csv_path))
    generate_html(all_cashflows, args.template, str(out_html_path))
    
    # 提取即期汇率
    fx_rates = extract_spot_rates(args.points_csv)
    generate_horizon_summary_html(all_cashflows, all_pnl, fx_rates, 
                                  args.template_summary, str(out_html_summary_path))
    
    print(f"处理完成！")
    print(f"- 聚合现金流: {out_csv_path}")
    print(f"- 现金流报告: {out_html_path}")
    print(f"- 期限汇总: {out_html_summary_path}")
    print(f"- 处理交易数: {len(trades)}")
    print(f"- 现金流记录数: {len(all_cashflows)}")


if __name__ == '__main__':
    main()
