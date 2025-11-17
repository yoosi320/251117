# sync_addressbooks_to_db.py

from typing import List, Dict, Any

from sqlalchemy.orm import Session

from db import SessionLocal, AddressBook

# 🔴 실제 프로젝트 구조에 맞게 import 경로/이름을 맞춰줘
from naver_commerce.store_manager import StoreManager
#from store_manager import store_manager        # 예: store_manager.get_store("BTF")

#from naver_commerce.client import NaverCommerceClient
from naver_commerce.client import get_all_addressbooks

manager = StoreManager("config/stores.json")


def fetch_addressbooks_for_store(store_code: str) -> List[Dict[str, Any]]:
    """
    store_manager를 통해 스토어 객체를 가져와서
    client.get_all_addressbooks() 로 전체 주소록 리스트를 조회.
    """
    store_name = "BTF"   # 또는 "WDS"
    client = manager.get_client(store_name)

 #   items = client.search_products(request_body)
    items = client.get_all_addressbooks(store_name)
    return items


def _extract_addressbook_no(item: Dict[str, Any]) -> str:
    """
    주소록 고유번호 필드 추출 (실제 응답 JSON에 맞게 수정)
    """
    return str(
        item.get("addressBookNo")
        or item.get("addressId")
        or item.get("id")
        or ""
    )


def sync_addressbooks_for_store(db: Session, store_code: str) -> int:
    """
    하나의 스토어(BTF 또는 WDS)에 대한 주소록을
    API에서 가져와 AddressBook 테이블에 upsert.
    """
    items = fetch_addressbooks_for_store(store_code)
    saved_count = 0

    for item in items:
        api_no = _extract_addressbook_no(item)
        if not api_no:
            continue

        existing: AddressBook | None = (
            db.query(AddressBook)
            .filter(
                AddressBook.store_code == store_code,
                AddressBook.api_addressbook_no == api_no,
            )
            .first()
        )

        # 🔴 여기는 실제 응답 JSON 키 이름에 맞게만 한 번 확인하면 됨
        address_name = item.get("addressBookName") or item.get("addressName")
        receiver_name = item.get("receiverName")
        zip_code = item.get("zipCode")
        base_address = item.get("baseAddress") or item.get("address")
        detail_address = item.get("detailAddress")
        phone = item.get("phoneNumber") or item.get("phone")
        mobile = item.get("mobileNumber") or item.get("mobile")
        is_default = (item.get("defaultYn") == "Y") or (item.get("isDefault") is True)
        usable = (item.get("usableYn") == "Y") or (item.get("usable") is True)

        if existing:
            existing.address_name = address_name
            existing.receiver_name = receiver_name
            existing.zip_code = zip_code
            existing.base_address = base_address
            existing.detail_address = detail_address
            existing.phone = phone
            existing.mobile = mobile
            existing.is_default = is_default
            existing.usable = usable
        else:
            new_item = AddressBook(
                store_code=store_code,
                api_addressbook_no=api_no,
                address_name=address_name,
                receiver_name=receiver_name,
                zip_code=zip_code,
                base_address=base_address,
                detail_address=detail_address,
                phone=phone,
                mobile=mobile,
                is_default=is_default,
                usable=usable,
            )
            db.add(new_item)

        saved_count += 1

    db.commit()
    return saved_count


def sync_addressbooks_for_btf_and_wds() -> dict:
    """
    BTF / WDS 두 스토어를 한 번에 동기화
    - /backup-addresses 엔드포인트에서 이 함수만 호출하면 됨
    """
    db = SessionLocal()
    try:
        btf = sync_addressbooks_for_store(db, "BTF")
        wds = sync_addressbooks_for_store(db, "WDS")
        return {"BTF": btf, "WDS": wds}
    finally:
        db.close()
