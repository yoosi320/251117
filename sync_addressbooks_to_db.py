"""
sync_addressbooks_to_db.py

네이버 커머스 API '주소록 목록 조회'(/v1/seller/addressbooks-for-page)를 호출해서
주소록(addressBookNo 기준)을 SQLite DB에 저장하는 스크립트.

사용 예시:
    python sync_addressbooks_to_db.py --store BTF
    python sync_addressbooks_to_db.py --store WDS
"""

import argparse
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

import bcrypt
import pybase64
import requests


# -----------------------------
# 1. 설정값 (여기만 본인 환경에 맞게 수정)
# -----------------------------

# 커머스 API 애플리케이션 ID / 시크릿
CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "6WS4EOiuSBGKyVj4RveM34")
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "YOUR_CLIENT_SE$2a$04$FLUuWl120vOxLxKFlobbTuCRET_HERE")

# type: SELF 또는 SELLER
#  - 스토어 판매자 계정 기준이면 보통 SELLER + account_id 사용
AUTH_TYPE = os.getenv("NAVER_AUTH_TYPE", "SELLER")

# SELLER 타입일 때 판매자 ID (통합매니저에서 쓰는 seller id)
ACCOUNT_ID = os.getenv("NAVER_ACCOUNT_ID", "YOUR_ACCOUNT_ID_HERE")

# DB 파일 경로
DB_PATH = os.getenv("ADDRESSBOOK_DB_PATH", "./naver_addressbooks.db")

# 커머스 API 기본 URL
BASE_URL = "https://api.commerce.naver.com"


# -----------------------------
# 2. 인증 토큰 발급
#    (공식 문서 / 블로그 예제 기반) :contentReference[oaicite:0]{index=0}
# -----------------------------

def get_access_token(
    client_id: str,
    client_secret: str,
    auth_type: str = "SELLER",
    account_id: Optional[str] = None,
) -> str:
    """
    OAuth2 Client Credentials 방식으로 인증 토큰 발급.
    - /external/v1/oauth2/token
    - client_secret_sign 전자서명(bcrypt + base64) 사용
    """
    if auth_type == "SELLER" and not account_id:
        raise ValueError("AUTH_TYPE=SELLER 인 경우 ACCOUNT_ID 가 필요합니다.")

    # 1) timestamp (밀리초)
    timestamp = str(int(time.time() * 1000))

    # 2) password = client_id + "_" + timestamp
    password = f"{client_id}_{timestamp}"

    # 3) bcrypt 해싱 (salt에 client_secret 사용)
    hashed = bcrypt.hashpw(password.encode("utf-8"), client_secret.encode("utf-8"))

    # 4) base64 인코딩
    client_secret_sign = pybase64.standard_b64encode(hashed).decode("utf-8")

    # 5) 토큰 발급 요청
    token_url = f"{BASE_URL}/external/v1/oauth2/token"
    params = {
        "client_id": client_id,
        "timestamp": timestamp,
        "client_secret_sign": client_secret_sign,
        "grant_type": "client_credentials",
        "type": auth_type,
    }
    # SELLER 타입이면 account_id 필요
    if auth_type == "SELLER":
        params["account_id"] = account_id

    headers = {"content-type": "application/x-www-form-urlencoded"}

    resp = requests.post(token_url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if "access_token" not in data:
        raise RuntimeError(f"토큰 발급 실패: {data}")

    return data["access_token"]


# -----------------------------
# 3. 주소록 목록 조회 (/v1/seller/addressbooks-for-page)
# -----------------------------

def fetch_all_addressbooks(access_token: str) -> List[Dict[str, Any]]:
    """
    /v1/seller/addressbooks-for-page 를 1페이지부터 끝까지 돌면서
    모든 주소록을 리스트로 반환.
    페이지당 100개 고정. :contentReference[oaicite:1]{index=1}
    """
    all_items: List[Dict[str, Any]] = []
    page = 1

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    while True:
        url = f"{BASE_URL}/v1/seller/addressbooks-for-page"
        resp = requests.get(url, headers=headers, params={"page": page}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # 응답 구조는 문서에 상세 예시가 없어서, 대표적인 패턴 몇 개를 순서대로 시도
        items = (
            data.get("content")
            or data.get("addressBooks")
            or data.get("items")
            or data.get("data")
            or []
        )

        if not isinstance(items, list):
            raise RuntimeError(
                f"예상과 다른 주소록 응답 구조입니다. data keys = {list(data.keys())}"
            )

        all_items.extend(items)

        # 페이지 정보 추론: Spring page 응답 패턴 가정 (page/totalPages/last 등)
        last = data.get("last")
        total_pages = data.get("totalPages")
        if last is True:
            break
        if isinstance(total_pages, int) and page >= total_pages:
            break

        # totalPages 정보가 없으면, items 갯수가 0일 때 종료
        if not items and total_pages is None:
            break

        page += 1

    return all_items


# -----------------------------
# 4. SQLite DB 초기화 & UPSERT
# -----------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """
    SQLite DB 생성 및 테이블 준비.
    address_book 테이블 구조:
      - store: BTF / WDS 등
      - address_book_no: 네이버 addressBookNo (shippingAddressId/returnAddressId 로 사용)
      - name, zip_code, base_address, detail_address: 보조 정보
      - raw_json: 전체 JSON 저장
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS address_book (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            store           TEXT NOT NULL,
            address_book_no INTEGER NOT NULL,
            name            TEXT,
            zip_code        TEXT,
            base_address    TEXT,
            detail_address  TEXT,
            raw_json        TEXT,
            UNIQUE(store, address_book_no)
        )
        """
    )
    conn.commit()
    return conn


def upsert_addressbooks(
    conn: sqlite3.Connection,
    store: str,
    addressbooks: List[Dict[str, Any]],
) -> int:
    """
    주소록 리스트를 address_book 테이블에 upsert.
    - store + address_book_no 기준으로 INSERT or REPLACE
    """
    cur = conn.cursor()
    count = 0

    for ab in addressbooks:
        address_book_no = ab.get("addressBookNo")
        if address_book_no is None:
            # 혹시 응답 구조가 다를 경우를 대비해 로그만 남기고 스킵
            print(f"[WARN] addressBookNo 없음, 원본: {ab}")
            continue

        # 필드 이름은 실제 응답에 맞게 한 번만 확인해서 조정해주면 됨
        name = ab.get("name") or ab.get("addressBookName")
        zip_code = ab.get("zipCode") or ab.get("zip")
        base_address = ab.get("baseAddress") or ab.get("address")
        detail_address = ab.get("detailAddress") or ab.get("detail")

        raw_json = json.dumps(ab, ensure_ascii=False)

        cur.execute(
            """
            INSERT INTO address_book (
                store, address_book_no, name, zip_code,
                base_address, detail_address, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(store, address_book_no) DO UPDATE SET
                name = excluded.name,
                zip_code = excluded.zip_code,
                base_address = excluded.base_address,
                detail_address = excluded.detail_address,
                raw_json = excluded.raw_json
            """,
            (
                store,
                int(address_book_no),
                name,
                zip_code,
                base_address,
                detail_address,
                raw_json,
            ),
        )
        count += 1

    conn.commit()
    return count


# -----------------------------
# 5. 메인 함수
# -----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="네이버 커머스 API 주소록을 DB로 동기화하는 스크립트"
    )
    parser.add_argument(
        "--store",
        required=True,
        help="스토어 이름 (예: BTF, WDS 등. DB에 구분용으로 저장)",
    )
    args = parser.parse_args()

    store = args.store

    if CLIENT_ID.startswith("YOUR_") or CLIENT_SECRET.startswith("YOUR_"):
        raise SystemExit(
            "먼저 스크립트 상단의 CLIENT_ID / CLIENT_SECRET / ACCOUNT_ID 값을 설정해 주세요."
        )

    print(f"[INFO] 토큰 발급 중... (type={AUTH_TYPE}, account_id={ACCOUNT_ID})")
    token = get_access_token(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        auth_type=AUTH_TYPE,
        account_id=ACCOUNT_ID,
    )
    print("[INFO] 토큰 발급 완료")

    print("[INFO] 주소록 전체 조회 중...")
    addressbooks = fetch_all_addressbooks(token)
    print(f"[INFO] 주소록 {len(addressbooks)}건 조회")

    print(f"[INFO] DB({DB_PATH}) 연결 및 테이블 준비...")
    conn = init_db(DB_PATH)

    print(f"[INFO] DB에 address_book upsert 중... (store={store})")
    saved = upsert_addressbooks(conn, store, addressbooks)
    print(f"[INFO] 저장/업데이트 완료: {saved}건")

    conn.close()
    print("[DONE] 주소록 동기화가 완료되었습니다.")


if __name__ == "__main__":
    main()
