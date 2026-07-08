"""Tests for src.config.Settings — defaults & new embedding/chroma fields."""
from src.config import Settings


def test_settings_has_embedding_defaults():
    s = Settings()
    assert s.embedding_provider == "api"
    assert s.embedding_model == ""
    assert s.chroma_path == "src/rag/chroma_db"
    assert s.chroma_collection == "popmart_knowledge"