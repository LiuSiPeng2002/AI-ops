from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "mysql+aiomysql://root:000000@192.168.100.5:30306/ai_ops"

    # JWT
    jwt_secret: str = "ai-ops-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 7

    # K8s Master (SSH)
    k8s_master_host: str = "192.168.100.5"
    k8s_master_port: int = 22
    k8s_master_user: str = "root"
    k8s_master_password: str = "000000"

    # LLM
    openai_api_key: str = "sk-your-api-key"
    openai_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    # Embedding (Ollama)
    embedding_base_url: str = "http://localhost:11434/v1"
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_api_key: str = "sk-your-api-key"

    # Prometheus
    prometheus_url: str = ""

    # DingTalk Notification
    dingtalk_enabled: bool = True
    dingtalk_webhook_url: str = "https://oapi.dingtalk.com/robot/send?access_token=698d3429b800a0912d3fb1e22ac7bd6897a19cd2574fb9c3558c15abd969a7d9"
    dingtalk_secret: str = ""
    dingtalk_notify_on_anomaly: bool = True
    dingtalk_notify_on_remedy: bool = True
    dingtalk_notify_on_verify_fail: bool = True
    dingtalk_notify_on_loop_exhausted: bool = True

    # --- Performance ---
    # Database connection pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 3600

    # LLM / HTTP
    llm_request_timeout: int = 120          # seconds
    llm_max_retries: int = 2
    llm_max_concurrency: int = 5            # max concurrent LLM calls

    # Tool execution
    tool_exec_timeout: int = 45             # seconds for kubectl/SSH commands
    tool_max_retries: int = 1

    # --- Security ---
    # Fields to mask in audit logs (case-insensitive substring match)
    sensitive_field_patterns: list[str] = [
        "password", "secret", "token", "api_key", "apikey",
        "access_token", "refresh_token", "jwt_secret",
    ]
    # Maximum command length (reject longer commands)
    max_command_length: int = 2000

    # --- Error handling ---
    # Circuit breaker: max consecutive failures before degradation
    circuit_breaker_failures: int = 5
    circuit_breaker_window: int = 60         # seconds

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "protected_namespaces": (),
    }


settings = Settings()
