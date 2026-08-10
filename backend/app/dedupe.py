from __future__ import annotations

import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Mapping


MERCHANT_NOISE = re.compile(r"股份有限公司|有限公司|企業社|分公司|門市部|門市|信用卡消費|簽帳消費|一般消費|消費款|交易")


def normalize_merchant(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).upper()
    normalized = MERCHANT_NOISE.sub("", normalized)
    return "".join(char for char in normalized if char.isalnum() or "\u3400" <= char <= "\u9fff")


def merchant_similarity(left: str, right: str) -> float:
    a, b = normalize_merchant(left), normalize_merchant(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 3 and (a in b or b in a):
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def is_duplicate(candidate: Mapping[str, object], existing: Mapping[str, object]) -> bool:
    if candidate["type"] != existing["type"]:
        return False
    if abs(float(candidate["amount"]) - float(existing["amount"])) > 0.01:
        return False
    days = abs((date.fromisoformat(str(candidate["date"])) - date.fromisoformat(str(existing["date"]))).days)
    similarity = merchant_similarity(str(candidate["title"]), str(existing["title"]))
    if days == 0 and similarity >= 0.9:
        return True
    carrier_pair = candidate["source"] == "雲端發票" or existing["source"] == "雲端發票"
    return bool(carrier_pair and days <= 3 and similarity >= 0.82)
