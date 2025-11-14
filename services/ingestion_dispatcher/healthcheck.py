"""Simple healthcheck to verify RabbitMQ connectivity."""
from __future__ import annotations

import os
import sys

import pika


def main() -> int:
    rabbit_url = os.getenv("RABBITMQ_URL", "amqp://ingest:ingest@rabbitmq:5672/")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
        try:
            channel = connection.channel()
            channel.basic_qos(prefetch_count=1)
        finally:
            connection.close()
    except Exception as exc:  # pragma: no cover - run-time diagnostic
        print(f"[healthcheck] RabbitMQ unavailable: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
