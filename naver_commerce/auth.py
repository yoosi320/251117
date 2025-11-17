import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
import pybase64
import requests


TOKEN_URL = "https://api.commerce.naver.com/external/v1/oauth2/token"


@dataclass
class NaverStoreConfig:
    """
    한 개 스마트스토어(또는 판매자)에 대한 설정 정보
    """
    name: str
    client_id: str
    client_secret: str
    type: str = "SELF"              # SELF 또는 SELLER
    account_id: Optional[str] = None  # type=SELLER일 때만 사용


class NaverCommerceAuth:
    """
    네이버 커머스 API 인증 토큰 발급/캐시 담당 클래스
    """

    def __init__(self, config: NaverStoreConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._expires_at: Optional[float] = None  # epoch seconds

    def _generate_signature(self) -> tuple[str, str]:
        """
        bcrypt + base64 전자서명(client_secret_sign) 생성

        timestamp는 밀리초 단위 문자열
        password = client_id + "_" + timestamp
        hashed = bcrypt.hashpw(password, client_secret)
        client_secret_sign = base64(bcrypt 결과)
        """
        # timestamp는 살짝 과거 시간으로 쓰는 예제가 많아서 -3초 정도 보정
        timestamp = str(int((time.time() - 3) * 1000))
        password = f"{self.config.client_id}_{timestamp}"

        hashed = bcrypt.hashpw(
            password.encode("utf-8"),
            self.config.client_secret.encode("utf-8"),
        )
        signature = pybase64.standard_b64encode(hashed).decode("utf-8")
        return timestamp, signature

    def _request_new_token(self) -> str:
        """
        네이버 커머스 API에서 새 access_token 발급
        """
        timestamp, signature = self._generate_signature()

        data = {
            "client_id": self.config.client_id,
            "timestamp": timestamp,
            "client_secret_sign": signature,
            "grant_type": "client_credentials",
            "type": self.config.type,  # SELF 또는 SELLER
        }
        if self.config.type == "SELLER" and self.config.account_id:
            data["account_id"] = self.config.account_id

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        # form-data 방식으로 POST
        resp = requests.post(TOKEN_URL, data=data, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"토큰 발급 실패: {resp.status_code} {resp.text}"
            )

        body = resp.json()
        access_token = body["access_token"]
        expires_in = body.get("expires_in", 10800)  # 기본 3시간

        # 만료 10분 전에 갱신되도록
        self._access_token = access_token
        self._expires_at = time.time() + expires_in - 600

        return access_token

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        유효한 토큰이 있으면 재사용, 아니면 새로 발급
        """
        if (
            not force_refresh
            and self._access_token
            and self._expires_at
            and time.time() < self._expires_at
        ):
            return self._access_token

        return self._request_new_token()
