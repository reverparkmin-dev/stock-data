import json
import os
from datetime import datetime

def calc_growth(current, previous):
    if previous in (0, None):
        return None
    return round((current - previous) / previous * 100, 2)

def calc_margin(profit, revenue):
    if revenue in (0, None):
        return None
    return round(profit / revenue * 100, 2)

def build_sample_data():
    # 샘플 원천 데이터
    ticker = "005930"
    name = "삼성전자"

    revenue = 302_231_400_000_000
    prev_revenue = 258_935_500_000_000
    operating_profit = 6_567_000_000_000

    result = {
        "ticker": ticker,
        "name": name,
        "revenue": revenue,
        "prev_revenue": prev_revenue,
        "revenue_growth_pct": calc_growth(revenue, prev_revenue),
        "operating_profit": operating_profit,
        "op_margin_pct": calc_margin(operating_profit, revenue),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d")
    }

    os.makedirs("data", exist_ok=True)

    output_path = f"data/{ticker}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"saved: {output_path}")

if __name__ == "__main__":
    build_sample_data()
