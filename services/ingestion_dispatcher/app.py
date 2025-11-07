import json
import logging
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Iterable, List, Optional
from urllib.parse import unquote_plus

import boto3
import httpx
import pika
from tenacity import retry, stop_after_attempt, wait_fixed

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOGGER = logging.getLogger("cognee-dispatcher")


@dataclass(frozen=True)
class Record:
    bucket: str
    key: str
    project_id: str
    category: str
    dataset: str


class S3Client:
    def __init__(self) -> None:
        self.default_bucket = os.getenv("S3_BUCKET", "projects")
        session = boto3.session.Session()
        self.client = session.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
            region_name=os.getenv("S3_REGION", "us-east-1"),
        )

    @contextmanager
    def download(self, key: str, bucket: Optional[str] = None):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        try:
            target_bucket = bucket or self.default_bucket
            self.client.download_file(target_bucket, key, tmp.name)
            yield tmp.name
        finally:
            try:
                os.unlink(tmp.name)
            except FileNotFoundError:
                pass


class CogneeApiClient:
    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._token: Optional[str] = None
        self._client = httpx.Client(timeout=httpx.Timeout(180.0))

    def close(self) -> None:
        self._client.close()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def ensure_authenticated(self) -> None:
        if self._token:
            return
        if not self._login():
            LOGGER.info("Registering new Cognee user %s", self.email)
            self._register()
            if not self._login():  # pragma: no cover
                raise RuntimeError("Unable to authenticate with Cognee service")

    def _register(self) -> None:
        response = self._client.post(
            f"{self.base_url}/api/v1/auth/register",
            json={"email": self.email, "password": self.password},
        )
        if response.status_code not in (200, 201, 400):
            response.raise_for_status()

    def _login(self) -> bool:
        response = self._client.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": self.email, "password": self.password},
        )
        if response.status_code != 200:
            return False
        self._token = response.json().get("access_token")
        self._client.headers["Authorization"] = f"Bearer {self._token}"
        return True

    def add_file(self, file_path: str, dataset: str) -> None:
        with open(file_path, "rb") as fh:
            files = {"data": (os.path.basename(file_path), fh)}
            data = {"datasetName": dataset}
            response = self._client.post(f"{self.base_url}/api/v1/add", data=data, files=files)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Add failed: {response.text}")

    def cognify(self, dataset: str) -> None:
        payload = {"datasets": [dataset], "run_in_background": False}
        response = self._client.post(f"{self.base_url}/api/v1/cognify", json=payload)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Cognify failed: {response.text}")


class Dispatcher:
    def __init__(self) -> None:
        self.s3 = S3Client()
        self.cognee_url = os.getenv("COGNEE_SERVICE_URL", "http://fuzzforge-cognee:8000")
        self.email_domain = os.getenv("EMAIL_DOMAIN", "fuzzforge.dev")
        self.category_map = self._parse_category_map(os.getenv("DATASET_CATEGORY_MAP"))

    @staticmethod
    def _parse_category_map(raw: Optional[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        if not raw:
            return mapping
        for pair in raw.split(","):
            if ":" not in pair:
                continue
            category, suffix = pair.split(":", 1)
            mapping[category.strip()] = suffix.strip()
        return mapping

    def handle_record(self, record: Record) -> None:
        LOGGER.info("Processing %s -> dataset %s", record.key, record.dataset)
        with self.s3.download(record.key, record.bucket) as local_path:
            client = CogneeApiClient(
                base_url=self.cognee_url,
                email=self._service_email(record.project_id),
                password=self._service_password(record.project_id),
            )
            try:
                client.ensure_authenticated()
                client.add_file(local_path, record.dataset)
                client.cognify(record.dataset)
            finally:
                client.close()

    def _service_email(self, project_id: str) -> str:
        return f"project_{project_id}@{self.email_domain}"

    def _service_password(self, project_id: str) -> str:
        return sha256(project_id.encode()).hexdigest()[:20]

    def parse_records(self, payload: Dict) -> Iterable[Record]:
        for record in payload.get("Records", []):
            s3_info = record.get("s3", {})
            bucket = s3_info.get("bucket", {}).get("name")
            key = unquote_plus(s3_info.get("object", {}).get("key", ""))
            key_parts = key.split("/")
            if len(key_parts) < 3:
                LOGGER.debug("Skipping key without project/category: %s", key)
                continue
            project_id, category = key_parts[0], key_parts[1]
            filename = key_parts[-1]
            if filename.startswith("tmp") and "." not in filename:
                LOGGER.debug("Skipping temporary upload key: %s", key)
                continue
            dataset_suffix = self.category_map.get(category)
            if not dataset_suffix:
                LOGGER.debug("Ignoring category %s for %s", category, key)
                continue
            dataset = f"{project_id}_{dataset_suffix}"
            yield Record(bucket=bucket or self.s3.default_bucket, key="/".join(key_parts), project_id=project_id, category=category, dataset=dataset)


def main() -> None:
    dispatcher = Dispatcher()
    rabbit_url = os.getenv("RABBITMQ_URL", "amqp://ingest:ingest@rabbitmq:5672/")
    exchange = os.getenv("RABBITMQ_EXCHANGE", "cognee-ingest")
    queue_name = os.getenv("RABBITMQ_QUEUE", "cognee-ingestion-dispatcher")

    connection = pika.BlockingConnection(pika.URLParameters(rabbit_url))
    channel = connection.channel()
    channel.exchange_declare(exchange=exchange, exchange_type="fanout", durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(queue=queue_name, exchange=exchange)
    channel.basic_qos(prefetch_count=1)

    def _callback(ch, method, _properties, body):
        try:
            payload = json.loads(body.decode("utf-8"))
            for record in dispatcher.parse_records(payload):
                dispatcher.handle_record(record)
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("Failed to process event: %s", exc)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=_callback)
    LOGGER.info("Ingestion dispatcher listening on %s", queue_name)
    channel.start_consuming()


if __name__ == "__main__":
    main()
