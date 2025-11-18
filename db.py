# db.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Text,
    BigInteger,
    DateTime,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# SQLite 파일을 data/naver_commerce.db 로 생성
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{DATA_DIR / 'naver_commerce.db'}"

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    store = Column(String(50), index=True)

    origin_product_no = Column(BigInteger, index=True)
    channel_product_no = Column(BigInteger, index=True)

    name = Column(String(500))
    status = Column(String(50))
    sale_price = Column(Integer)
    discounted_price = Column(Integer)
    stock_quantity = Column(Integer)

    category_id = Column(String(100))
    category_name = Column(String(500))

    brand_name = Column(String(200))
    model_name = Column(String(200))
    manufacturer_name = Column(String(200))

    reg_date = Column(DateTime, nullable=True)
    modified_date = Column(DateTime, nullable=True)

    raw_json = Column(Text)


    def to_dict(self):
        return {
            "id": self.id,
            "store": self.store,
            "origin_product_no": self.origin_product_no,
            "channel_product_no": self.channel_product_no,
            "name": self.name,
            "status": self.status,
            "sale_price": self.sale_price,
            "discounted_price": self.discounted_price,
            "stock_quantity": self.stock_quantity,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "brand_name": self.brand_name,
            "model_name": self.model_name,
            "manufacturer_name": self.manufacturer_name,
            "reg_date": self.reg_date,
            "modified_date": self.modified_date,
        }



class AddressBook(Base):
    __tablename__ = "address_books"

    # 네이버 주소록 고유번호
    addressBookNo = Column(Integer, primary_key=True, index=True)

    # API 필드 매핑
    name = Column(String(200))           # name
    addressType = Column(String(50))     # addressType (RELEASE / REFUND_OR_EXCHANGE / GENERAL 등)
    postalCode = Column(String(20))      # postalCode
    baseAddress = Column(String(200))    # baseAddress
    detailAddress = Column(String(200))  # detailAddress
    address = Column(String(300))        # address (전체 주소 문자열)

    phoneNumber1 = Column(String(50))    # phoneNumber1
    phoneNumber2 = Column(String(50))    # phoneNumber2

    hasLocation = Column(Boolean)        # hasLocation
    roadNameAddress = Column(Boolean)    # roadNameAddress
    overseasAddress = Column(Boolean)    # overseasAddress


class codeMapping(Base):
    __tablename__ = "codeMapping"

    # 네이버 주소록 고유번호
    id = Column(Integer, primary_key=True, index=True)

    # API 필드 매핑
    store = Column(String(200))           # name
    addressType = Column(String(50))     # addressType (RELEASE / REFUND_OR_EXCHANGE / GENERAL 등)
    postalCode = Column(String(20))      # postalCode
    baseAddress = Column(String(200))    # baseAddress
    detailAddress = Column(String(200))  # detailAddress
    address = Column(String(300))        # address (전체 주소 문자열)

    phoneNumber1 = Column(String(50))    # phoneNumber1
    phoneNumber2 = Column(String(50))    # phoneNumber2

    hasLocation = Column(Boolean)        # hasLocation
    roadNameAddress = Column(Boolean)    # roadNameAddress
    overseasAddress = Column(Boolean)    # overseasAddress


def init_db():
    Base.metadata.create_all(bind=engine)



def parse_iso_datetime(value: str | None) -> datetime | None:
    """
    네이버 답변 regDate/modifiedDate 같은 ISO 문자열을 Python datetime으로 변환
    예: "2023-08-02T16:18:51.405+09:00"
    """
    if not value:
        return None
    try:
        # +09:00 같은 타임존이 있어도 fromisoformat이 대부분 처리 가능
        return datetime.fromisoformat(value)
    except Exception:
        return None


def upsert_products(store: str, items: List[dict]):
    """
    네이버에서 받아온 contents 리스트를 받아서
    DB에 upsert(있으면 업데이트, 없으면 insert)
    """
    session = SessionLocal()
    try:
        for item in items:
            origin_product_no = item.get("originProductNo")
            channel_products = item.get("channelProducts") or []
            if not channel_products:
                continue
            ch = channel_products[0]

            channel_product_no = ch.get("channelProductNo")
            name = ch.get("name")
            status = ch.get("statusType")
            sale_price = ch.get("salePrice")
            discounted_price = ch.get("discountedPrice")
            stock_quantity = ch.get("stockQuantity")
            category_id = ch.get("categoryId")
            category_name = ch.get("wholeCategoryName")
            brand_name = ch.get("brandName")
            model_name = ch.get("modelName")
            manufacturer_name = ch.get("manufacturerName")
            reg_date = parse_iso_datetime(ch.get("regDate"))
            modified_date = parse_iso_datetime(ch.get("modifiedDate"))

            raw_json = json.dumps(item, ensure_ascii=False)

            # 기존 데이터 있는지 확인 (store + origin_product_no 기준)
            obj: Product | None = (
                session.query(Product)
                .filter(
                    Product.store == store,
                    Product.origin_product_no == origin_product_no,
                )
                .one_or_none()
            )

            if obj is None:
                obj = Product(
                    store=store,
                    origin_product_no=origin_product_no,
                    channel_product_no=channel_product_no,
                )
                session.add(obj)

            # 공통 필드 업데이트
            obj.channel_product_no = channel_product_no
            obj.name = name
            obj.status = status
            obj.sale_price = sale_price
            obj.discounted_price = discounted_price
            obj.stock_quantity = stock_quantity
            obj.category_id = category_id
            obj.category_name = category_name
            obj.brand_name = brand_name
            obj.model_name = model_name
            obj.manufacturer_name = manufacturer_name
            obj.reg_date = reg_date
            obj.modified_date = modified_date
            obj.raw_json = raw_json

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
