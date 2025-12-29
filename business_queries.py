import datetime
import re
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

DB_PATH = Path(__file__).resolve().parent / "converted.db"


def _db_exists() -> bool:
    return DB_PATH.exists()


def _safe_float(value: Optional[object]) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def format_currency(amount: float) -> str:
    return f"₹{amount:,.2f}"


def _extract_keywords(text: str) -> List[str]:
    if not text:
        return []
    return [match.upper() for match in re.findall(r"[A-Z0-9&]+", text.upper())]


def _run_query(query: str, params: Iterable[object] = ()) -> List[sqlite3.Row]:
    if not _db_exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def get_company_outstanding(company_name: str, include_negative: bool = False) -> List[dict]:
    keywords = _extract_keywords(company_name)
    if not keywords:
        return []
    clauses = " AND ".join(["UPPER(ANAM) LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]
    rows = _run_query(f"SELECT ANAM, CITY, STATE, BALANCE FROM AMAS WHERE {clauses}", params)
    results = []
    for row in rows:
        balance = _safe_float(row["BALANCE"])
        if not include_negative and balance <= 0:
            continue
        results.append(
            {
                "company": row["ANAM"],
                "location": ", ".join(filter(None, [row["CITY"], row["STATE"]])) or "(Unknown)",
                "balance": balance,
            }
        )
    return results


def get_state_outstanding(state: str, include_negative: bool = False) -> float:
    keywords = _extract_keywords(state)
    if not keywords:
        return 0.0
    clauses = " AND ".join(["UPPER(STATE) LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]
    rows = _run_query(f"SELECT BALANCE FROM AMAS WHERE {clauses}", params)
    total = 0.0
    for row in rows:
        balance = _safe_float(row["BALANCE"])
        if include_negative:
            total += balance
        else:
            total += max(balance, 0.0)
    return total


def _find_item_codes(pattern: str) -> List[str]:
    keywords = _extract_keywords(pattern)
    if not keywords:
        return []
    clause = " AND ".join(["(UPPER(IALIAS) LIKE ? OR UPPER(ICIMAS) LIKE ?)" for _ in keywords])
    params = []
    for kw in keywords:
        like = f"%{kw}%"
        params.extend([like, like])
    rows = _run_query(f"SELECT DISTINCT ICIMAS FROM IMAS WHERE {clause}", params)
    return [row["ICIMAS"] for row in rows if row["ICIMAS"]]


def _find_account_codes(pattern: str) -> List[str]:
    keywords = _extract_keywords(pattern)
    if not keywords:
        return []
    clause = " AND ".join(["UPPER(ANAM) LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]
    rows = _run_query(f"SELECT ACOD FROM AMAS WHERE {clause}", params)
    return [row["ACOD"] for row in rows if row["ACOD"]]


def get_purchase_summary(
    item_pattern: str,
    vendor_pattern: Optional[str] = None,
    year: Optional[str] = None,
) -> Optional[dict]:
    item_codes = _find_item_codes(item_pattern)
    if not item_codes:
        return None
    placeholders_items = ",".join(["?" for _ in item_codes])
    sql = f"""
        SELECT
            SUM(CAST(REPLACE(TRIM(SITM.IQSITM), ',', '') AS REAL)) AS total_qty,
            SUM(CAST(REPLACE(TRIM(SITM.IASITM), ',', '') AS REAL)) AS total_amt
        FROM SITM
        JOIN PRCH ON SITM.VHNO = PRCH.VHNO
        WHERE SITM.VHTY = 'Prch'
          AND SITM.ICSITM IN ({placeholders_items})
    """
    params: List[object] = [*item_codes]
    if vendor_pattern:
        account_codes = _find_account_codes(vendor_pattern)
        if not account_codes:
            return None
        placeholders_vendor = ",".join(["?" for _ in account_codes])
        sql += f" AND PRCH.VCPRCH IN ({placeholders_vendor})"
        params.extend(account_codes)
    if year:
        sql += " AND PRCH.BDPRCH LIKE ?"
        params.append(f"{year}%")
    rows = _run_query(sql, params)
    if not rows:
        return None
    row = rows[0]
    total_qty = _safe_float(row["total_qty"])
    total_amt = _safe_float(row["total_amt"])
    return {
        "item": item_pattern,
        "vendor": vendor_pattern,
        "year": year,
        "qty": total_qty,
        "amount": total_amt,
    }


def get_sales_for_month(month: int) -> List[dict]:
    month_str = f"{month:02d}"
    sql = """
        SELECT SUBSTR(BDSALE, 1, 4) AS year,
               SUM(CAST(REPLACE(TRIM(TOTAL1), ',', '') AS REAL)) AS total_amount
        FROM SALE
        WHERE SUBSTR(BDSALE, 6, 2) = ?
        GROUP BY year
        ORDER BY year
    """
    rows = _run_query(sql, (month_str,))
    return [{"year": row["year"], "amount": _safe_float(row["total_amount"])} for row in rows if row["year"]]


def get_expense_amount(keyword: str, location: Optional[str] = None, month: Optional[int] = None) -> float:
    keywords = _extract_keywords(keyword)
    if not keywords:
        return 0.0
    clauses = " OR ".join(["UPPER(AMAS.ANAM) LIKE ?" for _ in keywords])
    params: List[object] = [f"%{kw}%" for kw in keywords]
    sql = f"""
        SELECT SUM(CAST(REPLACE(TRIM(TMAS.AMNT), ',', '') AS REAL)) AS amount
        FROM TMAS
        JOIN AMAS ON TMAS.COD1 = AMAS.ACOD
        WHERE ({clauses})
    """
    if location:
        loc_keywords = _extract_keywords(location)
        loc_parts = []
        for loc in loc_keywords:
            loc_parts.append("(UPPER(AMAS.CITY) LIKE ? OR UPPER(AMAS.STATE) LIKE ?)")
            loc_like = f"%{loc}%"
            params.extend([loc_like, loc_like])
        if loc_parts:
            sql += " AND (" + " OR ".join(loc_parts) + ")"
    if month:
        sql += " AND SUBSTR(TMAS.DATE, 6, 2) = ?"
        params.append(f"{month:02d}")
    rows = _run_query(sql, params)
    if not rows:
        return 0.0
    return _safe_float(rows[0]["amount"])


def get_inventory_for_location(item_pattern: str, location_pattern: str) -> Optional[dict]:
    item_codes = _find_item_codes(item_pattern)
    if not item_codes:
        return None
    loc_keywords = _extract_keywords(location_pattern)
    if not loc_keywords:
        return None
    loc_clause = " OR ".join(["UPPER(DNDEPT) LIKE ?" for _ in loc_keywords])
    loc_params = [f"%{loc}%" for loc in loc_keywords]
    dept_rows = _run_query(f"SELECT DCDEPT FROM DEPT WHERE {loc_clause}", loc_params)
    dept_codes = [row["DCDEPT"] for row in dept_rows if row["DCDEPT"]]
    if not dept_codes:
        return None
    placeholders_dept = ",".join(["?" for _ in dept_codes])
    placeholders_item = ",".join(["?" for _ in item_codes])
    sql = f"SELECT SUM(CAST(REPLACE(TRIM(OSTQTY), ',', '') AS REAL)) AS qty FROM DEPI WHERE DCDEPI IN ({placeholders_dept}) AND ICDEPI IN ({placeholders_item})"
    params: List[object] = [*dept_codes, *item_codes]
    rows = _run_query(sql, params)
    if not rows:
        return None
    quantity = _safe_float(rows[0]["qty"])
    return {"item_pattern": item_pattern, "location": location_pattern, "qty": quantity}


def get_outstanding_over_days(days: int = 60, limit: int = 10, include_negative: bool = False) -> List[dict]:
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    rows = _run_query(
        "SELECT RMAS.DATE AS date, RMAS.BALANCE AS balance, AMAS.ANAM AS name, AMAS.CITY AS city, AMAS.STATE AS state FROM RMAS JOIN AMAS ON RMAS.ACOD = AMAS.ACOD"
    )
    results: List[dict] = []
    for row in rows:
        date_value = row["date"]
        if not date_value:
            continue
        try:
            record_date = datetime.date.fromisoformat(date_value.split(" ")[0])
        except ValueError:
            continue
        if record_date >= cutoff:
            continue
        balance = _safe_float(row["balance"])
        if not include_negative and balance <= 0:
            continue
        results.append(
            {
                "name": row["name"],
                "location": ", ".join(filter(None, [row["city"], row["state"]])) or "(Unknown)",
                "date": record_date.isoformat(),
                "balance": balance,
            }
        )
    results.sort(key=lambda entry: entry["balance"], reverse=True)
    return results[:limit]


def answer_business_question(question: str) -> Optional[str]:
    lowered = question.lower()
    include_negative = any(kw in lowered for kw in ("show negative", "include negative", "also show negative", "include credits", "show credits", "negative values", "credit balances"))
    if "outstanding" in lowered and "60" in lowered and "day" in lowered:
        aging = get_outstanding_over_days(60, include_negative=include_negative)
        if not aging:
            return "No outstanding payments older than 60 days were found."
        descriptor = "including" if include_negative else "excluding"
        lines = [f"Outstanding payments older than 60 days ({descriptor} negative balances):"]
        for entry in aging:
            lines.append(
                f"- {entry['name']} ({entry['location']}) on {entry['date']}: {format_currency(entry['balance'])}"
            )
        return "\n".join(lines)
    if "pvc resin" in lowered and "meera" in lowered:
        summary = get_purchase_summary("PVC resin", "Meera Polymers")
        if not summary:
            return "No PVC resin purchases from Meera Polymers were found."
        return (
            f"Total PVC resin purchases from Meera Polymers: Qty={summary['qty']:,.2f}, Amount={format_currency(summary['amount'])}"
        )
    if "ll purchase" in lowered and "2025" in lowered:
        summary = get_purchase_summary("LL", None, "2025")
        if not summary:
            return "No LL purchases recorded for 2025."
        return (
            f"Total LL purchases during 2025: Qty={summary['qty']:,.2f}, Amount={format_currency(summary['amount'])}"
        )
    if "hd purchase" in lowered and "2024" in lowered:
        summary = get_purchase_summary("HD", None, "2024")
        if not summary:
            return "No HD purchases recorded for 2024."
        return (
            f"Total HD purchases during 2024: Qty={summary['qty']:,.2f}, Amount={format_currency(summary['amount'])}"
        )
    if "total outstanding" in lowered and "bihar" in lowered:
        total = get_state_outstanding("Bihar", include_negative=include_negative)
        descriptor = "including" if include_negative else "excluding"
        return f"Total outstanding in Bihar ({descriptor} negative balances): {format_currency(total)}"
    if "total outstanding" in lowered and "tamil" in lowered:
        total = get_state_outstanding("Tamil Nadu", include_negative=include_negative)
        descriptor = "including" if include_negative else "excluding"
        return f"Total outstanding in Tamil Nadu ({descriptor} negative balances): {format_currency(total)}"
    if "ta" in lowered and "da" in lowered and "delhi" in lowered:
        amount = get_expense_amount("TA DA", "Delhi")
        return f"TA/DA expense for Delhi office: {format_currency(amount)}"
    if "sales" in lowered and "october" in lowered:
        sales = get_sales_for_month(10)
        if not sales:
            return "No sales found for October."
        lines = ["October sales by year:"]
        for row in sales:
            lines.append(f"- {row['year']}: {format_currency(row['amount'])}")
        return "\n".join(lines)
    if "electricity" in lowered and "august" in lowered:
        amount = get_expense_amount("Electricity", month=8)
        return f"Electricity bills for August: {format_currency(amount)}"
    if "inventory" in lowered and "pvc pipe" in lowered and "jaipur" in lowered:
        info = get_inventory_for_location("PVC pipe", "Jaipur")
        if not info:
            return "No Jaipur depot inventory found for PVC pipe."
        return f"Inventory of PVC pipe at Jaipur depot: {info['qty']:,.2f} units"
    if "outstanding" in lowered:
        match = re.search(r"outstanding (?:of|for) ([^,.?]+)", question, re.I)
        if match:
            company = match.group(1).strip()
            results = get_company_outstanding(company, include_negative=include_negative)
            if not results:
                return f"No outstanding balances found for {company}."
            descriptor = "including" if include_negative else "excluding"
            lines = [f"Outstanding for {company} ({descriptor} negative values):"]
            for entry in results:
                lines.append(
                    f"- {entry['company']} ({entry['location']}): {format_currency(entry['balance'])}"
                )
            return "\n".join(lines)
    return None