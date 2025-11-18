import json
import pandas as pd
from typing import List

from fastapi import FastAPI, Request, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from naver_commerce.store_manager import StoreManager
from naver_commerce.product_clone import build_clone_payload_from_channel_product
from db import init_db, SessionLocal, Product, upsert_products, AddressBook


app = FastAPI()
templates = Jinja2Templates(directory="templates")

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



store_manager = StoreManager("config/stores.json")

# ===== 여기부터 추가: 스토어별 배송 설정 =====

DELIVERY_CONFIG: dict[str, dict] = {
    # 예시) WDS 스토어용 배송 설정
    "WDS": {
        # "deliveryInfo": {
        #     # 사용 중인 택배사 코드 (예: CJGLS, HANJIN 등)
        #     "deliveryCompany": "CJGLS",

        #     # 필요하다면 기본 배송비 관련 설정도 여기에 추가 가능
        #     # "deliveryFee": {
        #     #     "deliveryFeeType": "PAY_ONCE", ...
        #     # },

        #     # 반품/교환 주소, 출고지 주소 등
        #     "claimDeliveryInfo": {
        #         # 아래 ID 값들은 **WDS 스토어 센터에서 실제 값으로 바꿔야 함**
        #         "shippingAddressId": 111111,  # 출고지/배송지 주소 ID
        #         "returnAddressId": 222222,    # 반품/교환 주소 ID
        #     },
        # }
    },

    # 필요하면 BTF도 따로 세팅 가능
    # "BTF": {...}
}




@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    스토어 선택 화면
    """
    store_names = store_manager.list_stores()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stores": store_names,
        },
    )


@app.get("/products", response_class=HTMLResponse)
async def view_products(
    request: Request,
    store: str = Query(..., description="스토어 이름"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    session = SessionLocal()
    try:
        base_query = (
            session.query(Product)
            .filter(~Product.category_name.contains("로봇"))
            .filter(~Product.category_name.contains("RC"))
            .filter(Product.store == store)
            .order_by(Product.origin_product_no.desc())
        )

        total_elements = base_query.count()
        total_pages = max((total_elements + size - 1) // size, 1)

        rows = (
            base_query
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

        # 스토어 목록 (타겟 스토어 선택용)
        store_names = store_manager.list_stores()
        other_stores = [s for s in store_names if s != store]
        default_target_store = other_stores[0] if other_stores else store

        return templates.TemplateResponse(
            "products.html",
            {
                "request": request,
                "store": store,
                "rows": rows,
                "page": page,
                "size": size,
                "total_elements": total_elements,
                "total_pages": total_pages,
                "stores": store_names,
                "default_target_store": default_target_store,
            },
        )
    finally:
        session.close()



@app.get("/sync", response_class=HTMLResponse)
async def sync_store(
    request: Request,
    store: str = Query(..., description="스토어 이름"),
):
    """
    선택한 스토어의 상품을 네이버 API에서 모두 불러와 DB에 저장(동기화)
    """
    client = store_manager.get_client(store)

    page = 1
    size = 100
    total_pages = 1

    while page <= total_pages:
        body = {
            "productStatusTypes": ["SALE"],
            "page": page,
            "size": size,
            "orderType": "NO",
            "periodType": "PROD_REG_DAY",
            "fromDate": "2000-01-01",
            "toDate": "2099-12-31",
        }
        products = client.search_products(body)

        contents = products.get("contents", [])
        total_pages = products.get("totalPages", 1)

        # ✅ 여기서 DB 저장
        upsert_products(store, contents)

        page += 1

    return RedirectResponse(
        url=f"/products?store={store}&page=1&size=20", status_code=302
    )

# ... 기존 app, templates, init_db, store_manager 그대로 ...


@app.get("/clone-preview-page", response_class=HTMLResponse)
async def clone_preview_page(
    request: Request,
    from_store: str,
    to_store: str,
    channel_product_no: int,
):
    """
    A(from_store) 상품을 B(to_store)로 복제할 때
    originProduct / smartstoreChannelProduct 내용을 HTML로 미리보기.
    """
    from_client = store_manager.get_client(from_store)

    # 1) 채널상품 상세 조회
    try:
        detail = from_client.get_channel_product(channel_product_no)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"from_store({from_store}) 채널상품 조회 실패: {e}",
        )

    # 2) payload 생성 (B 기준으로 실제 어떤 데이터가 갈지)
    delivery_override = DELIVERY_CONFIG.get(to_store)
    payload = build_clone_payload_from_channel_product(detail, delivery_override=delivery_override)

    origin = payload.get("originProduct", {})
    smart = payload.get("smartstoreChannelProduct", {})

    origin_json = json.dumps(origin, ensure_ascii=False, indent=2)
    smart_json = json.dumps(smart, ensure_ascii=False, indent=2)

    return templates.TemplateResponse(
        "clone_preview.html",
        {
            "request": request,
            "from_store": from_store,
            "to_store": to_store,
            "channel_product_no": channel_product_no,
            "origin": origin,
            "smart": smart,
            "origin_json": origin_json,
            "smart_json": smart_json,
        },
    )


@app.post("/batch-clone", response_class=HTMLResponse)
async def batch_clone(
    request: Request,
    from_store: str = Form(...),
    to_store: str = Form(...),
    channel_product_no: List[str] = Form([]),
):
    """
    체크박스로 선택한 여러 상품을 한 번에 복제하는 엔드포인트.
    """
    if not channel_product_no:
        # 아무 것도 선택 안 한 경우
        return templates.TemplateResponse(
            "batch_clone_result.html",
            {
                "request": request,
                "from_store": from_store,
                "to_store": to_store,
                "results": [],
                "message": "선택된 상품이 없습니다.",
            },
        )

    from_client = store_manager.get_client(from_store)
    to_client = store_manager.get_client(to_store)
    delivery_override = DELIVERY_CONFIG.get(to_store)

    results = []

    for cp_str in channel_product_no:
        try:
            cp_no = int(cp_str)
        except ValueError:
            results.append(
                {
                    "channel_product_no": cp_str,
                    "success": False,
                    "error": "channel_product_no가 숫자가 아닙니다.",
                    "result_json": "",
                }
            )
            continue

        try:
            detail = from_client.get_channel_product(cp_no)
            payload = build_clone_payload_from_channel_product(
                detail,
                delivery_override=delivery_override,
            )
            api_result = to_client.create_product_v2(payload)

            results.append(
                {
                    "channel_product_no": cp_no,
                    "success": True,
                    "error": "",
                    "result_json": json.dumps(api_result, ensure_ascii=False, indent=2),
                }
            )
        except Exception as e:
            results.append(
                {
                    "channel_product_no": cp_no,
                    "success": False,
                    "error": str(e),
                    "result_json": "",
                }
            )

    return templates.TemplateResponse(
        "batch_clone_result.html",
        {
            "request": request,
            "from_store": from_store,
            "to_store": to_store,
            "results": results,
            "message": None,
        },
    )




@app.get("/clone-product", response_class=JSONResponse)
async def clone_product(
    from_store: str,
    to_store: str,
    channel_product_no: int,
):
    """
    A(from_store) 스토어의 채널상품 1개를 조회해서
    B(to_store) 스토어에 실제로 신규 상품으로 등록한다.

    - from_store: 소스 스토어 이름 (예: BTF)
    - to_store: 타겟 스토어 이름 (예: WDS)
    - channel_product_no: A 스토어 채널상품 번호
    """
    # 1) 스토어별 클라이언트
    try:
        from_client = store_manager.get_client(from_store)
        to_client = store_manager.get_client(to_store)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2) A 스토어에서 채널상품 상세 조회
    try:
        detail = from_client.get_channel_product(channel_product_no)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"from_store({from_store}) 채널상품 조회 실패: {e}",
        )

    # 3) 타겟 스토어 배송 설정 가져오기 (없으면 None)
    delivery_override = DELIVERY_CONFIG.get(to_store)

    # 4) 복사용 payload 구성
    try:
        payload = build_clone_payload_from_channel_product(
            detail,
            delivery_override=delivery_override,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"복제용 payload 생성 실패: {e}",
        )

    # 5) B 스토어에 실제 상품 등록
    try:
        result = to_client.create_product_v2(payload)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"to_store({to_store}) 상품 등록 실패: {e}",
        )

    # 6) 결과 반환 (필요하면 payload 일부도 함께 반환)
    return {
        "from_store": from_store,
        "to_store": to_store,
        "channel_product_no_source": channel_product_no,
        "payload_summary": {
            "originProduct_name": payload.get("originProduct", {}).get("name"),
            "originProduct_categoryId": payload.get("originProduct", {}).get("categoryId"),
        },
        "result": result,  # 네이버 응답 전체
    }


@app.post("/backup-addresses")
def backup_addresses():
    manager = StoreManager("config/stores.json")
    store_name = "WDS"   # 또는 "WDS"
    client = manager.get_client(store_name)
    items = client.get_all_addressbooks(store_name)
    df = pd.DataFrame(items)
    df.set_index('addressBookNo',inplace=True)
    df.to_excel("./WDS_After2.xlsx")


    db = SessionLocal()
    for item in items:
        address_book_no = item["addressBookNo"]
        

        # 이미 있는지 확인 (있으면 업데이트, 없으면 신규 생성)
        obj = db.query(AddressBook).filter(
            AddressBook.addressBookNo == address_book_no
        ).first()

        if obj is None:
            obj = AddressBook(addressBookNo=address_book_no)
            db.add(obj)

        # 공통 필드 매핑
        obj.name = item.get("name")
        obj.addressType = item.get("addressType")
        obj.postalCode = item.get("postalCode")
        obj.baseAddress = item.get("baseAddress")
        obj.detailAddress = item.get("detailAddress")
        obj.address = item.get("address")

        obj.phoneNumber1 = item.get("phoneNumber1")
        obj.phoneNumber2 = item.get("phoneNumber2")

        obj.hasLocation = item.get("hasLocation")
        obj.roadNameAddress = item.get("roadNameAddress")
        obj.overseasAddress = item.get("overseasAddress")

    db.commit()


    #result = sync_addressbooks_for_btf_and_wds()
    return JSONResponse({"message": "주소록 백업 완료", "result": store_name})