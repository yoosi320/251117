from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .auth import NaverStoreConfig, NaverCommerceAuth
from .client import NaverCommerceClient


class StoreManager:
    """
    여러 스마트스토어 설정을 한 번에 로드하고
    각 스토어별 NaverCommerceClient를 관리하는 매니저 클래스
    """

    def __init__(self, config_path: str = "config/stores.json"):
        self.config_path = Path(config_path)
        self.store_configs: Dict[str, NaverStoreConfig] = {}
        self.clients: Dict[str, NaverCommerceClient] = {}

        self._load_configs()
        self._create_clients()

    def _load_configs(self) -> None:
        """
        config/stores.json 읽어서 NaverStoreConfig 딕셔너리로 변환
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"스토어 설정 파일을 찾을 수 없습니다: {self.config_path}"
            )

        with self.config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        stores_data = data.get("stores", [])
        if not stores_data:
            raise ValueError("stores.json 안에 'stores' 항목이 비어 있습니다.")

        for item in stores_data:
            name = item.get("name")
            if not name:
                raise ValueError("각 스토어 항목에는 'name'이 반드시 필요합니다.")

            cfg = NaverStoreConfig(
                name=name,
                client_id=item["client_id"],
                client_secret=item["client_secret"],
                type=item.get("type", "SELF"),
                account_id=item.get("account_id"),
            )
            self.store_configs[name] = cfg

    def _create_clients(self) -> None:
        """
        각 스토어 설정에 대해 Auth + Client 인스턴스 생성
        """
        for name, cfg in self.store_configs.items():
            auth = NaverCommerceAuth(cfg)
            client = NaverCommerceClient(auth)
            self.clients[name] = client

    def get_client(self, store_name: str) -> NaverCommerceClient:
        """
        스토어 이름으로 클라이언트 가져오기
        """
        if store_name not in self.clients:
            raise KeyError(
                f"등록되지 않은 스토어 이름입니다: {store_name}\n"
                f"사용 가능한 스토어: {list(self.clients.keys())}"
            )
        return self.clients[store_name]

    def list_stores(self) -> List[str]:
        """
        등록된 스토어 이름 목록
        """
        return list(self.clients.keys())
