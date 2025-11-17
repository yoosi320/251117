# debug_client.py

from naver_commerce.store_manager import StoreManager
from naver_commerce import client as client_module

print("client 모듈 경로:", client_module.__file__)

from naver_commerce.client import NaverCommerceClient

print("NaverCommerceClient 메서드 목록:")
print([m for m in dir(NaverCommerceClient) if not m.startswith("_")])
