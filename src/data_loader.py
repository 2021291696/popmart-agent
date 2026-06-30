"""数据预加载 + TTL 过期重抓。

启动时检查每个 JSON 文件的 mtime：
  - < TTL(24h) → 直接加载到内存
  - ≥ TTL → 调 scraper 重抓 → 失败回退到本地旧文件
查询时从内存缓存读取，零 IO。
"""
import json
import logging
import time
from pathlib import Path

from .error_handler import DataMissingError

log = logging.getLogger("rag")


class DataLoader:
    def __init__(self, data_dir: str, ttl_hours: int = 24):
        self.data_dir = Path(data_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.cache: dict[str, list] = {}

    def init(self, scrapers: dict = None) -> None:
        """启动预加载。scrapers: {"business": scrape_fn, ...}"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        for json_file in self.data_dir.glob("*.json"):
            if json_file.name in ("metrics.json",):
                continue  # metrics 不是数据源
            name = json_file.stem
            try:
                data = self._load_or_refresh(json_file, name, scrapers)
                self.cache[name] = data
            except Exception as e:
                log.error(f"加载 {name} 失败: {e}")
                # 回退：如果旧文件还在，用旧数据
                if json_file.exists():
                    self.cache[name] = self._read_json(json_file)
                    log.warning(f"  → 回退到本地旧文件 {json_file.name}")

    def _load_or_refresh(self, path: Path, name: str,
                         scrapers: dict = None) -> list:
        mtime = path.stat().st_mtime if path.exists() else 0
        age = time.time() - mtime

        if age < self.ttl_seconds and path.exists():
            log.info(f"{name}: TTL 内（{age/3600:.1f}h），直接加载")
            return self._read_json(path)

        # TTL 过期，尝试重抓
        if scrapers and name in scrapers:
            log.info(f"{name}: TTL 过期（{age/3600:.1f}h），重抓...")
            try:
                scrapers[name]()  # 调 scraper 函数
                return self._read_json(path)
            except Exception as e:
                log.error(f"  → 重抓失败: {e}，回退到本地旧文件")
                if path.exists():
                    return self._read_json(path)
                raise DataMissingError(f"{name} 无本地缓存且重抓失败")

        # 无 scraper 但文件存在
        if path.exists():
            log.warning(f"{name}: 无 scraper，用本地文件（已过期）")
            return self._read_json(path)

        raise DataMissingError(f"{name} 文件不存在: {path}")

    def _read_json(self, path: Path) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 统一为 list
        if isinstance(data, dict):
            return [data]
        return data

    def get(self, name: str) -> list:
        """获取缓存数据"""
        if name not in self.cache:
            raise DataMissingError(f"{name} 未加载")
        return self.cache[name]

    def get_all(self) -> dict[str, list]:
        return self.cache.copy()
