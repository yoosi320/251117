# naver_commerce/client.py

import json
from typing import Any, Dict, Optional

import requests

from .auth import NaverCommerceAuth


BASE_URL = "https://api.commerce.naver.com"


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
