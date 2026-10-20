# 포트원(PortOne) V2 서버 API (https://developers.portone.io) — 본인인증 결과 조회, 결제 조회·취소
# 프론트가 넘겨준 ID로 포트원 서버에 직접 결과를 물어보고, 포트원이 확인해 준 정보만 믿는다.
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings

PORTONE_API_URL = "https://api.portone.io"
# 본인인증을 마친 뒤 이 시간 안에 가입해야 한다 (오래된 인증 ID 재사용 방지)
VERIFICATION_VALID_MINUTES = 30


class PortOneError(Exception):
    pass


class PortOneNotFound(PortOneError):
    pass


def _parse_datetime(value: str) -> datetime:
    # 포트원은 "2024-01-01T00:00:00.000Z" 형태로 준다. DB에는 UTC naive로 저장한다
    # (Python 3.9 fromisoformat은 Z와 소수점 7자리 이상을 못 읽으므로 맞춰준다)
    value = re.sub(r"(\.\d{6})\d+", r"\1", value.replace("Z", "+00:00"))
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _call(method: str, path: str, body: Optional[dict] = None) -> dict:
    if not settings.PORTONE_API_SECRET:
        raise PortOneError("포트원 API 키가 설정되지 않았습니다")

    url = f"{PORTONE_API_URL}{path}"
    if settings.PORTONE_STORE_ID and method == "GET":
        url += "?" + urllib.parse.urlencode({"storeId": settings.PORTONE_STORE_ID})
    if settings.PORTONE_STORE_ID and body is not None:
        body = {**body, "storeId": settings.PORTONE_STORE_ID}
    req = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"PortOne {settings.PORTONE_API_SECRET}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            error = json.loads(e.read().decode("utf-8"))
        except ValueError:
            error = {}
        if e.code == 404:
            raise PortOneNotFound(error.get("type") or "NOT_FOUND")
        raise PortOneError(error.get("type") or error.get("message") or f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise PortOneError("포트원 서버에 연결할 수 없습니다")


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def get_verified_identity(identity_verification_id: str) -> dict:
    """인증이 완료된 본인인증이면 {name, phone, verified_at, ci, di} 를 돌려주고, 아니면 PortOneError"""
    try:
        data = _call("GET", f"/identity-verifications/{_quote(identity_verification_id)}")
    except PortOneNotFound:
        raise PortOneError("본인인증 내역을 찾을 수 없습니다")
    except PortOneError:
        raise PortOneError("본인인증 결과를 확인하지 못했습니다")

    if data.get("status") != "VERIFIED":
        raise PortOneError("본인인증이 완료되지 않았습니다")

    customer = data.get("verifiedCustomer") or {}
    phone = re.sub(r"\D", "", customer.get("phoneNumber") or "")
    if not phone:
        raise PortOneError("본인인증 결과에 휴대폰 번호가 없습니다")

    verified_at = _parse_datetime(data["verifiedAt"]) if data.get("verifiedAt") else datetime.now(timezone.utc).replace(tzinfo=None)
    if datetime.now(timezone.utc).replace(tzinfo=None) - verified_at > timedelta(minutes=VERIFICATION_VALID_MINUTES):
        raise PortOneError("본인인증 유효시간이 지났습니다. 다시 인증해주세요")

    return {
        "name": customer.get("name"),
        "phone": phone,
        "verified_at": verified_at,
        "ci": customer.get("ci"),
        "di": customer.get("di"),
    }


def get_payment(payment_id: str) -> Optional[dict]:
    """포트원 결제 건 조회. 결제창을 열지도 않아 포트원에 없는 결제면 None
    반환: {status: READY|PENDING|VIRTUAL_ACCOUNT_ISSUED|PAID|FAILED|PARTIAL_CANCELLED|CANCELLED, amount, currency, paid_at}"""
    try:
        data = _call("GET", f"/payments/{_quote(payment_id)}")
    except PortOneNotFound:
        return None
    return {
        "status": data.get("status"),
        "amount": (data.get("amount") or {}).get("total"),
        "currency": data.get("currency"),
        "paid_at": _parse_datetime(data["paidAt"]) if data.get("paidAt") else None,
    }


def cancel_payment(payment_id: str, reason: str) -> None:
    """결제 전액 취소. 이미 취소된 결제면 그냥 성공으로 본다"""
    try:
        _call("POST", f"/payments/{_quote(payment_id)}/cancel", {"reason": reason})
    except PortOneError as e:
        if str(e) == "PAYMENT_ALREADY_CANCELLED":
            return
        raise
