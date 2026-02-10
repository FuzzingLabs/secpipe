from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fuzzforge_common.storage.configuration import StorageConfiguration


def test_download_directory(
    storage_configuration: StorageConfiguration,
    boto3_client: Any,
    random_bucket: str,
    tmp_path: Path,
) -> None:
    """TODO."""
    bucket = random_bucket
    storage = storage_configuration.into_storage()

    d1 = tmp_path.joinpath("d1")
    f1 = d1.joinpath("f1")
    d2 = tmp_path.joinpath("d2")
    f2 = d2.joinpath("f2")
    d3 = d2.joinpath("d3")
    f3 = d3.joinpath("d3")

    d1.mkdir()
    d2.mkdir()
    d3.mkdir()
    f1.touch()
    f2.touch()
    f3.touch()

    for path in [f1, f2, f3]:
        key: Path = Path("assets", path.relative_to(other=tmp_path))
        boto3_client.upload_file(
            Bucket=bucket,
            Filename=str(path),
            Key=str(key),
        )

    path = storage.download_directory(bucket=bucket, directory="assets")

    assert path.is_file()
