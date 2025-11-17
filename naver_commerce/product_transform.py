# naver_commerce/product_transform.py

from __future__ import annotations

import json
from typing import Any, Dict

from db import Product


def build_internal_from_db_product(product: Product) -> Dict[str, Any]:
    """
    DB에 저장된 Product(SQLAlchemy 객체)를
    내부 공통 스키마(dict)로 변환하는 함수.

    - A 스토어에서 복사할 때, DB에 쌓여 있는 정보를 기준으로
      "이 상품은 어떤 상태인가?"를 한 눈에 보기 쉽게 바꿔주는 역할.
    - 이후 이 internal dict + 네이버 채널상품 상세 데이터를 조합해서
      B 스토어 등록용 payload를 만들 예정.
    """

    internal: Dict[str, Any] = {
        "store": product.store,
        "origin_product_no": product.origin_product_no,
        "channel_product_no": product.channel_product_no,
        "name": product.name,
        "status": product.status,
        "sale_price": product.sale_price,
        "discounted_price": product.discounted_price,
        "stock_quantity": product.stock_quantity,
        "category_id": product.category_id,
        "category_name": product.category_name,
        "brand_name": product.brand_name,
        "model_name": product.model_name,
        "manufacturer_name": product.manufacturer_name,
        "reg_date": product.reg_date.isoformat() if product.reg_date else None,
        "modified_date": product.modified_date.isoformat() if product.modified_date else None,
    }

    # raw_json 에는 네이버에서 받은 전체 JSON(원상품+채널상품 구조)이 들어 있음
    # 필요할 때 내부에서 바로 dict 로 쓸 수 있도록 파싱해 둠
    try:
        internal["raw"] = json.loads(product.raw_json) if product.raw_json else None
    except Exception:
        internal["raw"] = None

    return internal
