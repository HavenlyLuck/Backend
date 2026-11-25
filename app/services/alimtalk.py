# 솔라피(SOLAPI) 카카오 알림톡 발송 — https://developers.solapi.com
# 알림톡만 보낸다 (카카오톡을 못 받는 사람에게 문자로 대신 보내는 기능은 끈다: disableSms)
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

SEND_URL = "https://api.solapi.com/messages/v4/send"
TIMEOUT_SECONDS = 10

# 알림 종류 → 템플릿 ID 설정 이름. 라벨은 솔라피 콘솔의 템플릿 이름과 같게 둔다
KINDS = {
    "raffle_entered": "SOLAPI_TEMPLATE_RAFFLE_ENTERED",
    "raffle_sold_out": "SOLAPI_TEMPLATE_RAFFLE_SOLD_OUT",
    "raffle_failed": "SOLAPI_TEMPLATE_RAFFLE_FAILED",
    "shipped": "SOLAPI_TEMPLATE_SHIPPED",
}
KIND_LABELS = {
    "raffle_entered": "응모 완료",
    "raffle_sold_out": "응모 완성",
    "raffle_failed": "응모 실패(자동 취소)",
    "shipped": "배송 출발",
}


class AlimtalkError(Exception):
    """보내지 못함. retryable이면 잠시 뒤 다시 보내 볼 만하다 (네트워크·솔라피 서버 오류).
    throttled: 같은 번호로 짧은 시간에 연달아 보내 솔라피가 거부함 — 간격을 두고 다시 보내면 된다"""
    def __init__(self, message: str, retryable: bool = False, throttled: bool = False):
        super().__init__(message)
        self.retryable = retryable or throttled
        self.throttled = throttled


def is_configured() -> bool:
    return bool(settings.SOLAPI_API_KEY and settings.SOLAPI_API_SECRET and settings.SOLAPI_PF_ID)


def template_id(kind: str) -> Optional[str]:
    name = KINDS.get(kind)
    return (getattr(settings, name) or None) if name else None


# 알림 내용 → 템플릿 변수. 카카오에 검수받은 템플릿의 #{변수} 이름과 글자 하나까지 같아야 한다.
# 솔라피 콘솔의 템플릿 본문을 바꾸면 여기 이름도 같이 바꾼다.
#   응모 완료: #{회차명} #{수량} #{결제내역} #{판매수} #{전체수}
#   응모 완성: #{회차명} #{전체수} #{수량} #{추첨일시}
#   응모 실패(자동 취소): #{회차명} #{수량} #{환불내역}
#   배송 출발: #{상품명} #{택배사} #{송장번호}
def build_variables(kind: str, data: dict) -> dict:
    if kind == "raffle_entered":
        return {
            "#{회차명}": data["product_name"],
            "#{수량}": str(data["ticket_count"]),
            "#{결제내역}": data["payment"],
            "#{판매수}": str(data["sold"]),
            "#{전체수}": str(data["total"]),
        }
    if kind == "raffle_sold_out":
        return {
            "#{회차명}": data["product_name"],
            "#{전체수}": str(data["total"]),
            "#{수량}": str(data["ticket_count"]),
            "#{추첨일시}": data["draw_at"],
        }
    if kind == "raffle_failed":
        return {
            "#{회차명}": data["product_name"],
            "#{수량}": str(data["ticket_count"]),
            "#{환불내역}": data["refund"],
        }
    if kind == "shipped":
        return {
            "#{상품명}": data["product_name"],
            "#{택배사}": data["carrier"],
            "#{송장번호}": data["tracking_number"],
        }
    raise ValueError(f"unknown alimtalk kind: {kind}")


def _auth_header() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt = secrets.token_hex(16)
    signature = hmac.new(
        settings.SOLAPI_API_SECRET.encode(), (date + salt).encode(), hashlib.sha256,
    ).hexdigest()
    return f"HMAC-SHA256 apiKey={settings.SOLAPI_API_KEY}, date={date}, salt={salt}, signature={signature}"


def send(to: str, template: str, variables: dict) -> str:
    """알림톡 1건을 솔라피에 접수한다. 반환: 솔라피 메시지 ID.
    접수(statusCode 2000)까지만 확인한다 — 실제 카카오톡 도착 여부는 솔라피 콘솔의 메시지 내역에서 본다"""
    body = {
        "message": {
            "to": to,
            "type": "ATA",
            "kakaoOptions": {
                "pfId": settings.SOLAPI_PF_ID,
                "templateId": template,
                "variables": variables,
                "disableSms": True,
            },
        }
    }
    req = urllib.request.Request(
        SEND_URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
            message = f"{err.get('errorCode', e.code)}: {err.get('errorMessage', '')}"
        except ValueError:
            message = f"HTTP {e.code}"
        raise AlimtalkError(message, retryable=e.code >= 500, throttled=e.code == 429 or "반복 발송" in message)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise AlimtalkError(f"솔라피 연결 실패: {e}", retryable=True)

    status = str(data.get("statusCode", ""))
    if status != "2000":
        raise AlimtalkError(f"{status}: {data.get('statusMessage', '')}")
    return str(data.get("messageId", ""))
