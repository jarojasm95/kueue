from pydantic import BaseSettings, Field


class KueueConfig(BaseSettings):
    class Config:
        env_prefix = "KUEUE_"

    kafka: str = Field("kafka.default.svc.cluster.local:9092", env="KAFKA")
