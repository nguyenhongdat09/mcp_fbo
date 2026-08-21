"""Automated keyword builder for logic_hints in SQL procedure summaries."""

from __future__ import annotations

import re
from typing import Any

# Infrastructure keywords
INFRA_KEYWORDS = {"Partition$Execute", "sp_executesql", "WHILE", "CURSOR", "#report"}

# Common report parameters frequently appearing in FastBusiness SQL procedures
COMMON_REPORT_PARAMS = {
    "@DateFrom", "@DateTo", "@Unit", "@Customer", "@Item", "@Site", "@Account",
    "@Language", "@Form", "@mau_bc", "@Status", "@CalculateTransfer",
    "@ReportType", "@DataType", "@Controller", "@DynamicKeyTable", "@Key",
    "@thang_tu", "@thang_den", "@nam_tu", "@nam_den", "@ma_dvcs", "@ma_bp",
    "@ma_vv", "@ma_kh", "@ma_vt", "@ma_kho", "@kieu_xem", "@kieu_dt",
}

# Regex patterns for business parameters
PARAM_PATTERNS = [
    re.compile(r"^@\w+_yn$", re.I),
    re.compile(r"^@(loai|source|phan_loai|ticket|Type|Action|status|kieu_\w+|kieu)$", re.I),
]

DOMAIN_SEEDS: dict[str, list[str]] = {
    "interest_related": ["tl_th", "tl_qh", "@Status", "@days", "ctdmku", "m_kieu_ls", "m_ngay_ls_nam", "so_du", "lai_thang"],
    "bctc_form_related": ["@form", "@mau_bc", "bcnsky", "glns", "dmctns", "CheckFormula", "JobCalcXStruct", "cach_tinh", "ty_trong"],
    "input_invoice_related": ["InputInvoice", "ImportXml", "IIInsert", "@ticket"],
    "einvoice_related": ["EInvoice", "hddt", "Publish", "GetInvoice"],
    "approval_related": ["@Status", "Approve", "APV", "LoadApproval", "GetApprovalRole"],
    "discount_related": ["Discount", "ck_", "ty_le", "Allocation"],
    "post_related": ["@Site", "@Item", "sl_", "ton_", "Partition$Execute", "INSERT", "UPDATE"],
    "voucher_lifecycle_related": ["@stt_rec", "stt_rec_", "sl_", "AfterUpdate", "BeforeUpdate", "fsdSttRecRef"],
    "balance_related": ["Balance$", "#$bal", "so_du", "ton_"],
    "stock_related": ["Balance$Lot", "@CalculateTransfer", "m_instock_split", "ton_", "sl_", "dmvt", "dmlo"],
    "custom_action_related": ["@stt_rec", "@Action", "@Status", "#$tmp", "INSERT INTO", "UPDATE"],
    "custom_report_related": ["@stt_rec", "#cap_duyet", "zcdmsignature", "chu_ky", "PIVOT", "m89$", "d89$", "@KeyPO", "#$da_tao", "zcdmtb0", "#$tmp", "dmkh", "@DateFrom", "@DateTo"],
    "custom_listing_related": ["@KeyPO", "#$da_tao", "zcdmtb0", "#$tmp", "dmkh"],
    "custom_related": ["@KeyPO", "#$tmp", "@stt_rec", "dmkh"],
    "report_generic": ["@DateFrom", "@DateTo", "@Key", "@q", "Partition$Execute", "#report"],
}


def build_keywords_suggested(
    full_text: str,
    params: list[Any],
    temp_tables: list[str] | set[str],
    tables_read: list[str] | set[str],
    calls_direct: list[Any],
    domain_flag: str | None = None,
) -> list[str]:
    """Auto-extract suggested keywords from proc context without hardcoding per procedure."""
    txt = full_text.lower()
    out: list[str] = []

    def add(k: str) -> None:
        if k and k not in out:
            out.append(k)

    # A) Params: common + pattern matched + present in body
    for p in params:
        p_name = p.name if hasattr(p, "name") else str(p)
        if p_name in COMMON_REPORT_PARAMS or any(r.match(p_name) for r in PARAM_PATTERNS):
            if p_name.lower() in txt:
                add(p_name)

    # B) Temp tables #... and #$...
    for t in sorted(temp_tables):
        if t.startswith("#"):
            add(t)

    # C) Characteristic tables (partition rNN$, dNN$, zc*, dm*)
    for t in sorted(tables_read):
        if re.match(r"^[rdcm]\d\d\$", t) or t.startswith("zc") or t.startswith("dm"):
            add(t)

    # D) Infra calls (bare name)
    for c in calls_direct:
        c_name = c.name if hasattr(c, "name") else str(c)
        bare = c_name.split(".")[-1]
        if bare in (
            "FastBusiness$Balance$Lot",
            "FastBusiness$Balance$BContract",
            "FastBusiness$Report$CheckFormula",
            "FastBusiness$Report$GetDynamicKey",
            "FastBusiness$Partition$Execute",
        ):
            add(bare)

    # E) Domain-specific seeds
    if domain_flag and domain_flag in DOMAIN_SEEDS:
        for kw in DOMAIN_SEEDS[domain_flag]:
            if kw.lower() in txt:
                add(kw)

    # F) Signal keywords
    if "while" in txt:
        add("WHILE")
    if "cursor" in txt:
        add("CURSOR")

    return out[:20]  # Cap to 20 keywords
