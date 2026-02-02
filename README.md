# fx-cashflow-converter

外汇交易现金流转换工具 - 从外汇交易明细生成现金流报告。

## 功能特性

- ✅ 支持 Spot（现汇）、FX Swap（外汇掉期）、Outright Forward（远期）三种交易类型
- ✅ 现金流自动计算与聚合
- ✅ 远期点插值计算
- ✅ P&L 损益计算
- ✅ CSV 和 HTML 双格式输出
- ✅ 文件夹过滤功能
- ✅ 即期汇率提取

## 安装

```bash
git clone https://github.com/JasperLai/fx-cashflow-converter.git
cd fx-cashflow-converter
```

## 使用方法

### 基础用法

```bash
python cashflow_convertor_standard.py --input dataSource/tradeDetail.csv
```

### 完整参数

```bash
python cashflow_convertor_standard.py \
  --input dataSource/tradeDetail.csv \
  --points_csv dataSource/fwd_points_sample.csv \
  --ignore_folders "JSH_SWPPOS,ZF-FXSWAP" \
  --filter_config dataSource/filter.json \
  --out_dir generatedFile
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | 必填 | 交易明细 CSV 文件路径 |
| `--points_csv` | 空 | 远期点报表 CSV 路径 |
| `--ignore_folders` | 空 | 忽略的文件夹列表（逗号分隔） |
| `--filter_config` | 空 | 过滤规则 JSON 文件 |
| `--out_dir` | `generatedFile` | 输出目录 |
| `--out_csv` | `cashflows_agg.csv` | 聚合现金流输出文件名 |
| `--out_html` | `cashflows.html` | 现金流 HTML 输出文件名 |
| `--out_html_summary` | `cashflows_horizon_summary.html` | 期限汇总 HTML 输出 |

## 输入数据格式

### 交易明细 (tradeDetail.csv)

| 字段名 | 必填 | 说明 |
|--------|------|------|
| Deal Id | ✅ | 交易唯一标识 |
| Type of Deal | ✅ | 交易类型：FX Swap / Spot / Outright Forward |
| Security | ✅ | 货币对，格式：`货币1/货币2` |
| Amount1 | ✅ | 标的货币金额 |
| Amount2 | ✅ | 计价货币金额 |
| Value Date | ✅ | 起息日，格式：`DD/MM/YYYY` |
| Mat. Date | | 远端到期日 |
| Rate/Price | | 汇率/远期点数 |
| Folder | | 交易组合/文件夹名称 |

### 远期点报表 (fwd_points_sample.csv)

```
<货币对>
Tenor,SettlementDate,BidPoints,AskPoints,BidOutright,AskOutright
SP,2026/1/2,7.0350,7.0450,7.0350,7.0450
1M,2026/2/2,7.1200,7.1300,7.1200,7.1300
```

### 过滤配置 (filter.json)

```json
{
  "ignore_folders": ["JSH_SWPPOS", "ZF-FXSWAP"]
}
```

## 输出示例

### 聚合现金流 CSV

```csv
Date,Currency,Cashflow
2025-12-25,JPY,1200000
2025-12-25,CNY,-53980.8
2025-12-29,USD,-100000000
2025-12-29,CNY,701070000
```

## 项目结构

```
fx-cashflow-converter/
├── cashflow_convertor_standard.py  # 主程序
├── points_interpolator.py           # 远期点插值模块
├── dataSource/                      # 示例数据目录
│   ├── tradeDetail.csv             # 交易明细
│   ├── fwd_points_sample.csv       # 远期点报表
│   └── filter.json                 # 过滤配置
├── templates/                      # HTML 模板
│   ├── template.html               # 现金流模板
│   └── template_horizon_summary.html # 期限汇总模板
├── generatedFile/                  # 输出目录
└── README.md                       # 本文件
```

## 依赖

- Python 3.7+
- 无外部依赖（仅使用标准库）

## 许可

MIT License
