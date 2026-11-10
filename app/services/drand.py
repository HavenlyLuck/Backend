# drand 공개 난수 (https://drand.love) — 여러 기관이 함께 3초마다 만드는 공개 난수로 응모 당첨자를 뽑는다.
# 매진 시점에 "아직 나오지 않은 미래 라운드"를 정해 두고, 그 라운드 값이 나오면 그 값으로 추첨한다.
# 누구나 라운드 번호로 같은 값을 조회해 결과를 다시 계산할 수 있다.
import hashlib
import json
import logging
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# quicknet 체인 (3초 간격, League of Entropy 운영)
CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
GENESIS_TIME = 1692803367
PERIOD_SECONDS = 3

# 한 곳이 안 되면 다음 곳에 묻는다 (모두 같은 체인의 값을 중계한다)
RELAYS = (
    "https://api.drand.sh",
    "https://api2.drand.sh",
    "https://api3.drand.sh",
    "https://drand.cloudflare.com",
)
TIMEOUT_SECONDS = 5


class DrandUnavailable(Exception):
    """라운드가 아직 나오지 않았거나 모든 중계 서버에 닿지 못함 — 다음 주기에 다시 시도한다"""


def round_at(when: datetime) -> int:
    """when(UTC naive 또는 aware) 이후에 처음 나오는 라운드 번호. 라운드 r은 GENESIS_TIME + (r-1)*PERIOD에 나온다"""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    elapsed = when.timestamp() - GENESIS_TIME
    return max(1, math.ceil(elapsed / PERIOD_SECONDS) + 1)


def round_time(round_number: int) -> datetime:
    """라운드가 나오는 시각 (UTC naive)"""
    ts = GENESIS_TIME + (round_number - 1) * PERIOD_SECONDS
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def beacon_url(round_number: int, relay: str = RELAYS[0]) -> str:
    return f"{relay}/{CHAIN_HASH}/public/{round_number}"


def fetch_beacon(round_number: int) -> dict:
    """{"round", "randomness", "signature"}를 돌려준다. randomness가 sha256(signature)인지 확인한다"""
    last_error: Optional[Exception] = None
    for relay in RELAYS:
        try:
            req = urllib.request.Request(beacon_url(round_number, relay), headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_error = e
            continue

        randomness = str(data.get("randomness", "")).lower()
        signature = str(data.get("signature", "")).lower()
        if int(data.get("round", -1)) != round_number or not randomness or not signature:
            last_error = ValueError(f"unexpected drand response from {relay}")
            continue
        # quicknet은 randomness = sha256(signature) — 중계 서버가 값을 바꿔치기하지 않았는지 확인
        if hashlib.sha256(bytes.fromhex(signature)).hexdigest() != randomness:
            logging.warning("drand randomness mismatch from %s (round %s)", relay, round_number)
            last_error = ValueError("randomness != sha256(signature)")
            continue
        return {"round": round_number, "randomness": randomness, "signature": signature}

    raise DrandUnavailable(f"drand round {round_number} unavailable: {last_error}")


def pick_index(randomness_hex: str, total: int) -> int:
    """0 이상 total 미만의 칸 번호 = (난수를 정수로 본 값) mod total"""
    return int(randomness_hex, 16) % total
