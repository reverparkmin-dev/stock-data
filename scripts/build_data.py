import io
import json
import os
import zipfile
from datetime import datetime

import requests
import xml.etree.ElementTree as ET


API_KEY = os.getenv("DART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api"


# 조회할 종목
STOCKS = [
    {"ticker": "005930", "name": "삼성전자"},
    # {"ticker": "000660", "name": "SK하이닉스"},
    # {"ticker": "035420", "name": "NAVER"},
]

# 보고서 코드
REPORT_CODE = "11011"   # 사업보고서
BUSINESS_YEAR = "2024"  # 필요시 수정


def safe_int(value):
    if value is None:
        return None
    value = str(value).replace(",", "").strip()
    if value in ("", "-", "null"):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def calc_growth(current, previous):
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / previous * 100, 2)


def calc_margin(profit, revenue):
    if profit is None or revenue in (None, 0):
        return None
    return round(profit / revenue * 100, 2)


def download_corp_codes():
    url = f"{BASE_URL}/corpCode.xml"
    params = {"crtfc_key": API_KEY}

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        xml_filename = zf.namelist()[0]
        with zf.open(xml_filename) as xml_file:
            xml_bytes = xml_file.read()

    root = ET.fromstring(xml_bytes)
    mapping = {}

    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()

        if stock_code:
            mapping[stock_code] = {
                "corp_code": corp_code,
                "corp_name": corp_name,
            }

    return mapping


def fetch_major_accounts(corp_code, bsns_year, reprt_code):
    url = f"{BASE_URL}/fnlttSinglAcnt.json"
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
    }

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    status = data.get("status")
    if status != "000":
        raise RuntimeError(f"DART API 오류: {status} / {data.get('message')}")

    return data.get("list", [])


def pick_amount(item):
    # 사업보고서는 thstrm_amount, 분/반기에는 누적값 thstrm_add_amount가 더 유용한 경우가 많음
    return safe_int(item.get("thstrm_amount")) or safe_int(item.get("thstrm_add_amount"))


def pick_prev_amount(item):
    return safe_int(item.get("frmtrm_amount")) or safe_int(item.get("frmtrm_add_amount"))


def extract_metrics(rows):
    revenue = None
    prev_revenue = None
    operating_profit = None

    for row in rows:
        account_nm = (row.get("account_nm") or "").strip()
        sj_div = (row.get("sj_div") or "").strip()
        fs_div = (row.get("fs_div") or "").strip()

        # 연결재무제표 우선
        if fs_div != "CFS":
            continue

        # 손익계산서 중심
        if sj_div != "IS":
            continue

        # 매출액
        if account_nm in ("매출액", "수익(매출액)", "영업수익"):
            revenue = pick_amount(row)
            prev_revenue = pick_prev_amount(row)

        # 영업이익
        if account_nm in ("영업이익",):
            operating_profit = pick_amount(row)

    return {
        "revenue": revenue,
        "prev_revenue": prev_revenue,
        "operating_profit": operating_profit,
    }


def build_one_stock(stock, corp_map):
    ticker = stock["ticker"]
    display_name = stock["name"]

    if ticker not in corp_map:
        raise RuntimeError(f"{ticker}의 corp_code를 찾지 못했습니다.")

    corp_code = corp_map[ticker]["corp_code"]
    dart_name = corp_map[ticker]["corp_name"]

    rows = fetch_major_accounts(corp_code, BUSINESS_YEAR, REPORT_CODE)
    metrics = extract_metrics(rows)

    revenue = metrics["revenue"]
    prev_revenue = metrics["prev_revenue"]
    operating_profit = metrics["operating_profit"]

    result = {
        "ticker": ticker,
        "name": display_name,
        "dart_name": dart_name,
        "corp_code": corp_code,
        "business_year": BUSINESS_YEAR,
        "report_code": REPORT_CODE,
        "revenue": revenue,
        "prev_revenue": prev_revenue,
        "revenue_growth_pct": calc_growth(revenue, prev_revenue),
        "operating_profit": operating_profit,
        "op_margin_pct": calc_margin(operating_profit, revenue),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    os.makedirs("data", exist_ok=True)
    output_path = f"data/{ticker}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"saved: {output_path}")


def main():
    if not API_KEY:
        raise RuntimeError("환경변수 DART_API_KEY 가 없습니다.")

    corp_map = download_corp_codes()

    for stock in STOCKS:
        build_one_stock(stock, corp_map)


if __name__ == "__main__":
    main()
