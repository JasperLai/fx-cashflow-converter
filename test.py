import csv
import json
import argparse
from decimal import Decimal

# 测试配置
TEST_CONFIG = {
    "ignore_folders": ["JSH_SWPPOS", "ZF-FXSWAP"]
}

def test_parse_decimal():
    """测试数值解析"""
    from points_interpolator import points_divisor_by_pair
    
    assert points_divisor_by_pair("JPY/CNY") == 1000000
    assert points_divisor_by_pair("USD/CNY") == 10000
    assert points_divisor_by_pair("EUR/USD") == 10000
    print("✓ points_divisor_by_pair 测试通过")


def test_csv_parsing():
    """测试 CSV 解析"""
    import tempfile
    import os
    
    # 创建临时交易文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("""Deal Id,Type of Deal,Security,Amount1,Amount2,Value Date,Mat. Date,Rate/Price,Folder
VAL_IMP:7750129,Spot,JPY/CNY,1200000,-53980.8,25/12/2025,,,TRADER
VAL_IMP:2016522,FX Swap,USD/CNY,-100000000,701070000,29/12/2025,30/12/2025,-0.5,JSH_SWAP
""")
        temp_file = f.name
    
    try:
        trades = []
        with open(temp_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
        
        assert len(trades) == 2
        assert trades[0]['Deal Id'] == 'VAL_IMP:7750129'
        assert trades[1]['Type of Deal'] == 'FX Swap'
        print("✓ CSV 解析测试通过")
    finally:
        os.unlink(temp_file)


def test_filter_config():
    """测试过滤配置"""
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"ignore_folders": ["JSH_SWPPOS", "ZF-FXSWAP"]}')
        temp_file = f.name
    
    try:
        with open(temp_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert 'ignore_folders' in config
        assert len(config['ignore_folders']) == 2
        print("✓ 过滤配置测试通过")
    finally:
        os.unlink(temp_file)


if __name__ == '__main__':
    print("运行测试...")
    test_parse_decimal()
    test_csv_parsing()
    test_filter_config()
    print("\n所有测试通过！✓")
