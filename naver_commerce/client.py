# naver_commerce/client.py

import json
from typing import Any, Dict, Optional, List

import requests

from .auth import NaverCommerceAuth
# services/address_book.py
from sqlalchemy.orm import Session
from db import AddressBook

BASE_URL = "https://api.commerce.naver.com"
ADDRESSBOOK_LIST_PATH = "/external/v1/seller/addressbooks-for-page"
url = "https://api.commerce.naver.com/external/v1/seller/addressbooks-for-page"

payload = {}
headers = {
  'Accept': 'application/json',
  'Authorization': 'Bearer <token>'
}

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
    
    def get_addressbooks_page(
        self,   
        store_name: str,
        page: int = 1,
        size: int = 100,
    ) -> dict:
        params = {
            "page": page,
            "size": size,
        }

    # _request가 (method, path)만 받는 구조라서,
    # 쿼리스트링을 path에 직접 붙이는 방식으로 처리
        path = f"{ADDRESSBOOK_LIST_PATH}?page={page}"

    # ✅ 여기서 _request는 기존 다른 메서드들처럼 이렇게만 호출
        return self._request("GET", path)

    def get_all_addressbooks(
        self,
        store_name: str,
        page_size: int = 100,
    ) -> list[dict]:
        all_items: list[dict] = []
        page = 1

        while True:
            print("test1")
            data = self.get_addressbooks_page(store_name, page=page, size=page_size)
            contents = (
                data.get("contents")
                or data.get("data", {}).get("contents")
                or []
            )
            all_items.extend(data.get("addressBooks"))

          # 페이징 종료 조건 (응답 구조에 맞게 조정)
            last = data.get("last")
            total_pages = data.get("totalPage")
            has_next = data.get("hasNext")




#            if last is True:
 #               break
            if page >= total_pages:
                break
            #if has_next is False:
            #    break
  #          if not contents or len(contents) < page_size:
   #             break

            page += 1

        return all_items
    
    def test(self):
        print("test")
        response = self._request(
            "GET",
            "/external/v1/seller/addressbooks-for-page?page=2",
        )
        print("test2")
        print(response)



        


    
