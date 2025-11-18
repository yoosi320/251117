from naver_commerce.store_manager import StoreManager


def main():
    manager = StoreManager("config/stores.json")

    print("등록된 스토어 목록:")
    for name in manager.list_stores():
        print(" -", name)

    store_name = "BTF"   # 또는 "WDS"
    client = manager.get_client(store_name)

    request_body = {
        "productStatusTypes": ["SALE"],
        "page": 1,
        "size": 20,
        "orderType": "NO",
        "periodType": "PROD_REG_DAY",
        "fromDate": "2000-01-01",
        "toDate": "2099-12-31",
    }
    client.test()
    #print(products.text)
    products = client.search_products(request_body)
    
    
    print(f"\n[{store_name}] 상품 조회 결과:")

    contents = products.get("contents", [])
    total_count = products.get("totalElements", 0)   # ✅ totalCount → totalElements 로 수정
    print("totalElements(총 상품 수):", total_count)
    print("이번 페이지 가져온 상품 수:", len(contents))

    print("\n=== 앞 5개만 출력 ===")
    for item in contents[:5]:
        origin_product_no = item.get("originProductNo")
        channel_products = item.get("channelProducts", [])

        if not channel_products:
            print("-", origin_product_no, "(channelProducts 없음)")
            continue

        ch = channel_products[0]  # 대부분 1개이므로 첫 번째만 사용

        channel_product_no = ch.get("channelProductNo")
        name = ch.get("name")
        sale_price = ch.get("discountedPrice") or ch.get("salePrice")
        status = ch.get("statusType")

        print(
            f"- originNo={origin_product_no}, "
            f"channelNo={channel_product_no}, "
            f"name={name}, "
            f"price={sale_price}, "
            f"status={status}"
        )


if __name__ == "__main__":
    main()
