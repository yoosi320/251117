# naver_commerce/product_clone.py

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def build_clone_payload_from_channel_product(
    channel_product_detail: Dict[str, Any],
    *,
    delivery_override: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    채널상품 상세 응답(JSON)을 받아서
    POST /external/v2/products 용 payload(originProduct + smartstoreChannelProduct)를 구성한다.

    delivery_override:
      - B 스토어에서 사용할 배송/반품 주소, 배송비 템플릿 등을 덮어쓸 때 사용
      - 예: {
            "deliveryInfo": {
                "deliveryCompany": "CJGLS",
                "deliveryFee": {...},
                "claimDeliveryInfo": {
                    "shippingAddressId": 123456,
                    "returnAddressId": 123457,
                },
            }
        }
    """

    # 보통 채널상품 상세에는 이런 식으로 들어온다고 가정
    # {
    #   "originProduct": {...},
    #   "smartstoreChannelProduct": {...},
    #   ...
    # }
    origin = deepcopy(channel_product_detail.get("originProduct", {}))
    smart = deepcopy(channel_product_detail.get("smartstoreChannelProduct", {}))

    if not origin or not smart:
        raise ValueError("채널상품 상세 데이터에 originProduct/smartstoreChannelProduct가 없습니다.")

    # 1) 원상품 쪽에서 복사하면 안 되는 필드들 제거/정리 (번호, 상태 등)
    #    - 실제 필드는 카테고리/상품에 따라 다를 수 있으니, 우선 대표적인 것만 제거
    for key in [
        "originProductNo",
        "productNo",
        "statusType",  # 등록 시에는 SALE만 허용, 필요시 아래에서 강제 지정
        "saleStatusType",
        "saleStoppedAt",
        "createdDate",
        "updatedDate",
    ]:
        origin.pop(key, None)

    # 필수로 다시 넣어줄 값들 (상태/판매유형 등)
    # ※ saleType은 원래 값 유지, 없으면 NEW
    origin["statusType"] = "SALE"
    origin["saleType"] = origin.get("saleType", "NEW")

    # 1-1) 배송 주소 관련 ID 제거 (다른 스토어의 주소 ID는 신규 등록에 사용할 수 없음)
    delivery_info = origin.get("deliveryInfo") or {}
    if isinstance(delivery_info, dict):
        # 방문수령 주소 ID 제거
        delivery_info.pop("visitAddressId", None)

        claim_info = delivery_info.get("claimDeliveryInfo") or {}
        if isinstance(claim_info, dict):
            # 출고지/반품지 주소 ID 제거
            claim_info.pop("shippingAddressId", None)
            claim_info.pop("returnAddressId", None)
            delivery_info["claimDeliveryInfo"] = claim_info

        origin["deliveryInfo"] = delivery_info



# 1-1) 추가상품(supplementProducts) 내부 id 제거
    # A 스토어의 내부 id는 B 스토어 신규 상품 등록 시 사용하면 안 됨
    detail_attr = origin.get("detailAttribute") or {}
    supp_info = detail_attr.get("supplementProductInfo")
    if isinstance(supp_info, dict):
        supp_products = supp_info.get("supplementProducts") or []
        for sp in supp_products:
            if isinstance(sp, dict):
                # 네이버 에러에서 직접 지적한 필드
                sp.pop("id", None)
                # 혹시 모를 관련 id도 같이 제거(있으면)
                sp.pop("relationId", None)
        # 수정된 리스트를 다시 넣어주기 (습관적으로 한 번 더)
        supp_info["supplementProducts"] = supp_products
        detail_attr["supplementProductInfo"] = supp_info
        origin["detailAttribute"] = detail_attr

    # 1-2) 조합형 옵션(optionCombinations) 내부 id 제거
    # A 스토어 상품의 조합 옵션에 붙어있던 id는 B 스토어 신규 상품에서 사용할 수 없음
    option_info = detail_attr.get("optionInfo")
    if isinstance(option_info, dict):
        option_combinations = option_info.get("optionCombinations") or []
        for opt in option_combinations:
            if isinstance(opt, dict):
                opt.pop("id", None)           # 네이버가 오류로 짚어준 필드
                opt.pop("relationId", None)   # 혹시 있을 수 있는 연관 id도 같이 정리
        option_info["optionCombinations"] = option_combinations
        detail_attr["optionInfo"] = option_info
        origin["detailAttribute"] = detail_attr





    # 2) 채널상품 쪽도 번호/상태 일부 정리
    for key in [
        "channelProductNo",
        "productNo",
        "createdDate",
        "updatedDate",
    ]:
        smart.pop(key, None)

    # 판매 상태는 ON(노출) + SALE 조합으로 시작
    smart["channelProductDisplayStatusType"] = "ON"

    # 3) 배송 정보 오버라이드 (가장 중요한 스토어별 차이)
    #    - A 스토어의 배송/주소 ID는 B에 그대로 쓸 수 없음
    if delivery_override and "deliveryInfo" in delivery_override:
        origin.setdefault("deliveryInfo", {})
        merge_delivery_info(origin["deliveryInfo"], delivery_override["deliveryInfo"])

    # TODO: 필요하면 여기서 카테고리/속성/상품정보제공고시 등을 가공/보정할 수 있음

    payload = {
        "originProduct": origin,
        "smartstoreChannelProduct": smart,
    }
    return payload


def merge_delivery_info(target: Dict[str, Any], override: Dict[str, Any]) -> None:
    """
    deliveryInfo 안쪽에 있는 값들을 override로 덮어씌움.

    예:
      target = {
        "deliveryType": "...",
        "deliveryAttributeType": "...",
        "deliveryCompany": "CJGLS",
        "deliveryFee": {...},
        "claimDeliveryInfo": {...},
      }

      override = {
        "deliveryCompany": "CJGLS",
        "claimDeliveryInfo": {
          "shippingAddressId": 111,
          "returnAddressId": 222
        }
      }
    """
    for key, value in override.items():
        if isinstance(value, dict):
            # 중첩 dict는 재귀적으로 병합
            sub = target.get(key) or {}
            if not isinstance(sub, dict):
                sub = {}
            merge_delivery_info(sub, value)
            target[key] = sub
        else:
            target[key] = value
