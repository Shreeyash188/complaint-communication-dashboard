from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/complaints_db"
    synchronous_database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/complaints_db"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    similarity_threshold: float = 0.85
    llm_base_url: str = "https://api.openai.com/v1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
