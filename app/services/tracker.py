# 스마트택배(스윗트래커) 배송 조회 API (https://tracking.sweettracker.co.kr) 프록시
# 관리자가 발송 처리 때 고른 택배사 이름(Frontend/lib/adminShipping.ts의 CARRIERS)을 스마트택배 택배사 코드로 바꿔 조회한다
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from app.core.config import settings

TRACKING_API_URL = "https://info.sweettracker.co.kr/api/v1/trackingInfo"

# 택배사 이름 → 스마트택배 택배사 코드 (전체 목록: /api/v1/companylist)
CARRIER_CODES = {
    "우체국택배": "01",
    "CJ대한통운": "04",
    "한진택배": "05",
    "로젠택배": "06",
    "롯데택배": "08",
}

# 같은 송장을 짧은 시간에 여러 번 조회해도 API 호출은 한 번만 (호출 횟수 제한 대비)
CACHE_SECONDS = 300
_cache: dict[tuple[str, str], tuple[float, dict]] = {}


class TrackerError(Exception):
    pass


class TrackerNotConfigured(TrackerError):
    pass


def track(carrier: str, tracking_number: str) -> dict:
    """반환: {carrier, tracking_number, complete, level, estimate, details: [{time, where, kind, level}]} — details는 최신순.
    level: 1 배송준비 · 2 집화완료 · 3 배송중 · 4 지점 도착 · 5 배송출발 · 6 배송완료"""
    if not settings.SWEETTRACKER_API_KEY:
        raise TrackerNotConfigured("배송 조회 서비스가 아직 준비되지 않았어요")
    code = CARRIER_CODES.get(carrier)
    if not code:
        raise TrackerError(f"{carrier}는 배송 조회를 지원하지 않는 택배사예요")
    number = "".join(ch for ch in tracking_number if ch.isdigit())
    if not number:
        raise TrackerError("송장번호를 확인해 주세요")

    key = (code, number)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    query = urllib.parse.urlencode({"t_key": settings.SWEETTRACKER_API_KEY, "t_code": code, "t_invoice": number})
    try:
        with urllib.request.urlopen(f"{TRACKING_API_URL}?{query}", timeout=8) as res:
            data = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise TrackerError("배송 조회 서버에 연결할 수 없어요. 잠시 후 다시 시도해 주세요")

    # 실패하면 {"status": false, "code": "...", "msg": "..."}
    if data.get("status") is False or data.get("code"):
        msg = data.get("msg") or ""
        # 발송 처리 직후라 택배사에 아직 등록되지 않은 송장도 "유효하지 않은 운송장번호"로 온다
        if "운송장" in msg or "조회결과" in msg or "조회 결과" in msg:
            raise TrackerError("송장번호를 확인 중이에요. 발송 직후에는 택배사에 등록되기 전이라 조회가 안 될 수 있어요. 잠시 후 다시 확인해 주세요")
        # API 키 오류 등은 고객에게 그대로 보이지 않게 로그로만 남긴다
        logging.warning("sweettracker error code=%s msg=%s", data.get("code"), msg)
        raise TrackerError("배송 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요")

    details = [
        {
            "time": d.get("timeString") or "",
            "where": d.get("where") or "",
            "kind": d.get("kind") or "",
            "level": _int(d.get("level")),
        }
        for d in (data.get("trackingDetails") or [])
    ]
    details.reverse()
    result = {
        "carrier": carrier,
        "tracking_number": number,
        "complete": bool(data.get("complete")),
        "level": _int(data.get("level")),
        "estimate": data.get("estimate") or None,
        "details": details,
    }
    _cache[key] = (time.monotonic(), result)
    return result


def _int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
