# naver_commerce/client.py

import json
from typing import Any, Dict, Optional, List

import requests

from .auth import NaverCommerceAuth


BASE_URL = "https://api.commerce.naver.com"
ADDRESSBOOK_LIST_PATH = "/v1/seller/addressbooks-for-page"


class NaverCommerceClient:
    """
    네이버 커머스 API 공통 클라이언트
    - v1 상품 목록 조회
    - v2 채널상품/원상품 상세 조회
    - v2 상품 등록
    """

    def __init__(self, auth: NaverCommerceAuth):
        self.auth = auth

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        공통 HTTP 요청 래퍼
        """
        access_token = self.auth.get_access_token()
        url = BASE_URL + path

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        resp = requests.request(
            method.upper(),
            url,
            headers=headers,
            data=json.dumps(json_body) if json_body is not None else None,
        )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"API 오류: {resp.status_code} {resp.text}"
            )

        if not resp.text:
            return {}

        return resp.json()

    # === v1: 상품 목록 조회 ===
    def search_products(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        POST /external/v1/products/search
        """
        if body is None:
            body = {}

        return self._request(
            "POST",
            "/external/v1/products/search",
            json_body=body,
        )

    # === v2: 채널상품 상세 조회 ===
    def get_channel_product(self, channel_product_no: int) -> Dict[str, Any]:
        """
        GET /external/v2/products/channel-products/{channelProductNo}
        스마트스토어 채널 상품 상세 조회
        """
        path = f"/external/v2/products/channel-products/{channel_product_no}"
        return self._request("GET", path)

    # === v2: 원상품 상세 조회 ===
    def get_origin_product(self, origin_product_no: int) -> Dict[str, Any]:
        """
        GET /external/v2/products/origin-products/{originProductNo}
        원상품 상세 조회
        """
        path = f"/external/v2/products/origin-products/{origin_product_no}"
        return self._request("GET", path)

    # === v2: 상품 등록 ===
    def create_product_v2(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /external/v2/products
        originProduct + smartstoreChannelProduct 구조로 상품 등록
        """
        return self._request(
            "POST",
            "/external/v2/products",
            json_body=payload,
        )
    

#AddressBook
def get_addressbooks(
    store: Any,
    page: int = 0,
    size: int = 100,
    ) -> Dict[str, Any]:
    """
    단일 페이지의 주소록 목록을 가져온다.
    - store : store_manager에서 가져온 스토어 객체(BTF, WDS 등)
    - page  : 0부터 시작하는 페이지 번호
    - size  : 페이지당 개수
    """
    params = {
        "page": page,
        "size": size,
    }

    # ✅ 이 부분은 "상품 조회"에서 사용하는 호출 방식과 동일하게 맞춰줘
    resp = api_request(
#            store=store,   #yoosi
        method="GET",
        path=ADDRESSBOOK_LIST_PATH,
        params=params,
    )
    return resp


def get_all_addressbooks(store: Any, page_size: int = 100) -> List[Dict[str, Any]]:
    """
    페이징을 돌면서 해당 스토어의 모든 주소록을 리스트로 모아 준다.
    - 네이버 응답 JSON에 last / hasNext / totalPages 같은 필드가 있으면
    그걸 이용해서 반복 종료.
    """
    all_items: List[Dict[str, Any]] = []
    page = 0

    while True:
        data = get_addressbooks(store, page=page, size=page_size)

        contents = data.get("contents") or data.get("data", {}).get("contents") or []
        all_items.extend(contents)

        # 페이징 종료 조건은 실제 응답 구조에 맞게 조정
        last = data.get("last")
        total_pages = data.get("totalPages")
        has_next = data.get("hasNext")

        if last is True:
            break
        if total_pages is not None and page + 1 >= total_pages:
            break
        if has_next is False:
            break

        # 위 조건들이 전혀 없으면, contents 개수로 끝 판단(임시)
        if not contents or len(contents) < page_size:
            break

        page += 1

    return all_items


