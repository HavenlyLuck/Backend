# 행정안전부 도로명주소 검색 API (https://business.juso.go.kr) 프록시
import json
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings

JUSO_API_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"


class JusoError(Exception):
    pass


def search_address(keyword: str, page: int = 1, per_page: int = 10) -> dict:
    if not settings.JUSO_API_KEY:
        raise JusoError("주소 검색 API 키가 설정되지 않았습니다")

    query = urllib.parse.urlencode({
        "confmKey": settings.JUSO_API_KEY,
        "currentPage": page,
        "countPerPage": per_page,
        "keyword": keyword,
        "resultType": "json",
    })
    try:
        with urllib.request.urlopen(f"{JUSO_API_URL}?{query}", timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise JusoError("주소 검색 서버에 연결할 수 없습니다")

    results = data.get("results") or {}
    common = results.get("common") or {}
    if common.get("errorCode") != "0":
        raise JusoError(common.get("errorMessage") or "주소 검색에 실패했습니다")

    return {
        "total": int(common.get("totalCount") or 0),
        "page": page,
        "items": [
            {
                "zip_code": j.get("zipNo", ""),
                "road_address": j.get("roadAddr", ""),
                "jibun_address": j.get("jibunAddr", ""),
                "building_name": j.get("bdNm", ""),
            }
            for j in results.get("juso") or []
        ],
    }
