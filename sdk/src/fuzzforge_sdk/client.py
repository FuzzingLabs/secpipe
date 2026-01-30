"""
Main client class for interacting with the FuzzForge API.

Provides both synchronous and asynchronous methods for all API endpoints,
including real-time monitoring capabilities for fuzzing workflows.
"""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.


import asyncio
import json
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncIterator, Iterator, Union, Callable
from urllib.parse import urljoin, urlparse

import httpx
import websockets
try:
    from sseclient import SSEClient  # type: ignore
    _HAVE_SSECLIENT = True
except Exception:  # pragma: no cover
    SSEClient = None  # type: ignore
    _HAVE_SSECLIENT = False

try:
    import requests  # type: ignore
    _HAVE_REQUESTS = True
except Exception:  # pragma: no cover
    requests = None  # type: ignore
    _HAVE_REQUESTS = False

from .models import (
    APIStatus,
    WorkflowListItem,
    WorkflowMetadata,
    WorkflowParametersResponse,
    WorkflowSubmission,
    RunSubmissionResponse,
    WorkflowStatus,
    WorkflowFindings,
    FuzzingStats,
    CrashReport,
    WebSocketMessage,
    SSEMessage,
)
from .exceptions import (
    FuzzForgeError,
    FuzzForgeHTTPError,
    ConnectionError,
    TimeoutError,
    WebSocketError,
    SSEError,
    from_http_error,
)


logger = logging.getLogger(__name__)


class FuzzForgeClient:
    """
    Client for interacting with the FuzzForge API.

    Provides methods for workflow management, run monitoring, and real-time
    fuzzing statistics. Supports both synchronous and asynchronous operations.

    Args:
        base_url: Base URL of the FuzzForge API (e.g., "http://localhost:8000")
        timeout: Default timeout for HTTP requests in seconds
        verify_ssl: Whether to verify SSL certificates
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Create HTTP clients
        self._client = httpx.Client(timeout=timeout, verify=verify_ssl)
        self._async_client = httpx.AsyncClient(timeout=timeout, verify=verify_ssl)

        # WebSocket URL (convert http(s) to ws(s))
        parsed = urlparse(self.base_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        self._ws_base_url = f"{ws_scheme}://{parsed.netloc}"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    async def aclose(self):
        """Close the async HTTP client."""
        await self._async_client.aclose()

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions."""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise from_http_error(e.response.status_code, e.response.text, str(e.request.url))
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise FuzzForgeError(f"Invalid JSON response: {e}")

    async def _ahandle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle async HTTP response and raise appropriate exceptions."""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise from_http_error(e.response.status_code, e.response.text, str(e.request.url))
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            raise FuzzForgeError(f"Invalid JSON response: {e}")

    # Root API methods

    def get_api_status(self) -> APIStatus:
        """Get API status and information."""
        response = self._client.get(self.base_url)
        data = self._handle_response(response)
        return APIStatus(**data)

    async def aget_api_status(self) -> APIStatus:
        """Get API status and information (async)."""
        response = await self._async_client.get(self.base_url)
        data = await self._ahandle_response(response)
        return APIStatus(**data)

    # Workflow management methods

    def list_workflows(self) -> List[WorkflowListItem]:
        """List all available workflows."""
        url = urljoin(self.base_url, "/workflows/")
        response = self._client.get(url)
        data = self._handle_response(response)
        return [WorkflowListItem(**item) for item in data]

    async def alist_workflows(self) -> List[WorkflowListItem]:
        """List all available workflows (async)."""
        url = urljoin(self.base_url, "/workflows/")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return [WorkflowListItem(**item) for item in data]

    def get_workflow_metadata(self, workflow_name: str) -> WorkflowMetadata:
        """Get complete metadata for a workflow."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/metadata")
        response = self._client.get(url)
        data = self._handle_response(response)
        return WorkflowMetadata(**data)

    async def aget_workflow_metadata(self, workflow_name: str) -> WorkflowMetadata:
        """Get complete metadata for a workflow (async)."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/metadata")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return WorkflowMetadata(**data)

    def get_workflow_parameters(self, workflow_name: str) -> WorkflowParametersResponse:
        """Get parameters schema for a workflow."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/parameters")
        response = self._client.get(url)
        data = self._handle_response(response)
        return WorkflowParametersResponse(**data)

    async def aget_workflow_parameters(self, workflow_name: str) -> WorkflowParametersResponse:
        """Get parameters schema for a workflow (async)."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/parameters")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return WorkflowParametersResponse(**data)

    def get_metadata_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for workflow metadata files."""
        url = urljoin(self.base_url, "/workflows/metadata/schema")
        response = self._client.get(url)
        return self._handle_response(response)

    async def aget_metadata_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for workflow metadata files (async)."""
        url = urljoin(self.base_url, "/workflows/metadata/schema")
        response = await self._async_client.get(url)
        return await self._ahandle_response(response)

    def get_workflow_worker_info(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get worker information for a workflow.

        Returns details about which worker is required to execute this workflow,
        including container name, task queue, and vertical.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Dictionary with worker info including:
                - workflow: Workflow name
                - vertical: Worker vertical (e.g., "ossfuzz", "python", "rust")
                - worker_container: Docker container name
                - task_queue: Temporal task queue name
                - required: Whether worker is required (always True)

        Raises:
            FuzzForgeHTTPError: If workflow not found or metadata missing
        """
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/worker-info")
        response = self._client.get(url)
        return self._handle_response(response)

    async def aget_workflow_worker_info(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get worker information for a workflow (async).

        Returns details about which worker is required to execute this workflow,
        including container name, task queue, and vertical.

        Args:
            workflow_name: Name of the workflow

        Returns:
            Dictionary with worker info including:
                - workflow: Workflow name
                - vertical: Worker vertical (e.g., "ossfuzz", "python", "rust")
                - worker_container: Docker container name
                - task_queue: Temporal task queue name
                - required: Whether worker is required (always True)

        Raises:
            FuzzForgeHTTPError: If workflow not found or metadata missing
        """
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/worker-info")
        response = await self._async_client.get(url)
        return await self._ahandle_response(response)

    def submit_workflow(
        self,
        workflow_name: str,
        submission: WorkflowSubmission
    ) -> RunSubmissionResponse:
        """Submit a workflow for execution."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/submit")
        response = self._client.post(url, json=submission.model_dump())
        data = self._handle_response(response)
        return RunSubmissionResponse(**data)

    async def asubmit_workflow(
        self,
        workflow_name: str,
        submission: WorkflowSubmission
    ) -> RunSubmissionResponse:
        """Submit a workflow for execution (async)."""
        url = urljoin(self.base_url, f"/workflows/{workflow_name}/submit")
        response = await self._async_client.post(url, json=submission.model_dump())
        data = await self._ahandle_response(response)
        return RunSubmissionResponse(**data)

    def _create_tarball(
        self,
        source_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Path:
        """
        Create a compressed tarball from a file or directory.

        Args:
            source_path: Path to file or directory to archive
            progress_callback: Optional callback(bytes_written) for progress tracking

        Returns:
            Path to the created tarball

        Raises:
            FileNotFoundError: If source_path doesn't exist
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")

        # Create temp file for tarball
        temp_fd, temp_path = tempfile.mkstemp(suffix=".tar.gz")

        try:
            logger.info(f"Creating tarball from {source_path}")

            bytes_written = 0

            with tarfile.open(temp_path, "w:gz") as tar:
                if source_path.is_file():
                    # Add single file
                    tar.add(source_path, arcname=source_path.name)
                    bytes_written = source_path.stat().st_size
                    if progress_callback:
                        progress_callback(bytes_written)
                else:
                    # Add directory recursively
                    for item in source_path.rglob("*"):
                        if item.is_file():
                            arcname = item.relative_to(source_path)
                            tar.add(item, arcname=arcname)
                            bytes_written += item.stat().st_size
                            if progress_callback:
                                progress_callback(bytes_written)

            tarball_path = Path(temp_path)
            tarball_size = tarball_path.stat().st_size
            logger.info(
                f"Created tarball: {tarball_size / (1024**2):.2f} MB "
                f"(compressed from {bytes_written / (1024**2):.2f} MB)"
            )

            return tarball_path

        except Exception:
            # Cleanup on error
            if Path(temp_path).exists():
                Path(temp_path).unlink()
            raise

    def submit_workflow_with_upload(
        self,
        workflow_name: str,
        target_path: Union[str, Path],
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> RunSubmissionResponse:
        """
        Submit a workflow with file upload from local filesystem.

        This method automatically creates a tarball if target_path is a directory,
        uploads it to the backend, and submits the workflow for execution.

        Args:
            workflow_name: Name of the workflow to execute
            target_path: Local path to file or directory to analyze
            parameters: Workflow-specific parameters
            timeout: Timeout in seconds
            progress_callback: Optional callback(bytes_uploaded, total_bytes) for progress

        Returns:
            Run submission response with run_id

        Raises:
            FileNotFoundError: If target_path doesn't exist
            FuzzForgeHTTPError: For API errors
        """
        target_path = Path(target_path)
        tarball_path = None

        try:
            # Create tarball if needed
            if target_path.is_dir():
                logger.info("Target is directory, creating tarball...")
                tarball_path = self._create_tarball(target_path)
                upload_file = tarball_path
                filename = f"{target_path.name}.tar.gz"
            else:
                upload_file = target_path
                filename = target_path.name

            # Prepare multipart form data
            url = urljoin(self.base_url, f"/workflows/{workflow_name}/upload-and-submit")

            files = {
                "file": (filename, open(upload_file, "rb"), "application/gzip")
            }

            data = {}

            if parameters:
                data["parameters"] = json.dumps(parameters)

            if timeout:
                data["timeout"] = str(timeout)

            logger.info(f"Uploading {filename} to {workflow_name}...")

            # Track upload progress
            if progress_callback:
                file_size = upload_file.stat().st_size

                def track_progress(monitor):
                    progress_callback(monitor.bytes_read, file_size)

                # Note: httpx doesn't have built-in progress tracking for uploads
                # This is a placeholder - real implementation would need custom approach
                pass

            response = self._client.post(url, files=files, data=data)

            # Close file handle
            files["file"][1].close()

            data = self._handle_response(response)
            return RunSubmissionResponse(**data)

        finally:
            # Cleanup temporary tarball
            if tarball_path and tarball_path.exists():
                try:
                    tarball_path.unlink()
                    logger.debug(f"Cleaned up temporary tarball: {tarball_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup tarball {tarball_path}: {e}")

    async def asubmit_workflow_with_upload(
        self,
        workflow_name: str,
        target_path: Union[str, Path],
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> RunSubmissionResponse:
        """
        Submit a workflow with file upload from local filesystem (async).

        This method automatically creates a tarball if target_path is a directory,
        uploads it to the backend, and submits the workflow for execution.

        Args:
            workflow_name: Name of the workflow to execute
            target_path: Local path to file or directory to analyze
            parameters: Workflow-specific parameters
            timeout: Timeout in seconds
            progress_callback: Optional callback(bytes_uploaded, total_bytes) for progress

        Returns:
            Run submission response with run_id

        Raises:
            FileNotFoundError: If target_path doesn't exist
            FuzzForgeHTTPError: For API errors
        """
        target_path = Path(target_path)
        tarball_path = None

        try:
            # Create tarball if needed
            if target_path.is_dir():
                logger.info("Target is directory, creating tarball...")
                tarball_path = self._create_tarball(target_path)
                upload_file = tarball_path
                filename = f"{target_path.name}.tar.gz"
            else:
                upload_file = target_path
                filename = target_path.name

            # Prepare multipart form data
            url = urljoin(self.base_url, f"/workflows/{workflow_name}/upload-and-submit")

            files = {
                "file": (filename, open(upload_file, "rb"), "application/gzip")
            }

            data = {}

            if parameters:
                data["parameters"] = json.dumps(parameters)

            if timeout:
                data["timeout"] = str(timeout)

            logger.info(f"Uploading {filename} to {workflow_name}...")

            response = await self._async_client.post(url, files=files, data=data)

            # Close file handle
            files["file"][1].close()

            response_data = await self._ahandle_response(response)
            return RunSubmissionResponse(**response_data)

        finally:
            # Cleanup temporary tarball
            if tarball_path and tarball_path.exists():
                try:
                    tarball_path.unlink()
                    logger.debug(f"Cleaned up temporary tarball: {tarball_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup tarball {tarball_path}: {e}")

    # Run management methods

    def get_run_status(self, run_id: str) -> WorkflowStatus:
        """Get the status of a workflow run."""
        url = urljoin(self.base_url, f"/runs/{run_id}/status")
        response = self._client.get(url)
        data = self._handle_response(response)
        return WorkflowStatus(**data)

    async def aget_run_status(self, run_id: str) -> WorkflowStatus:
        """Get the status of a workflow run (async)."""
        url = urljoin(self.base_url, f"/runs/{run_id}/status")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return WorkflowStatus(**data)

    def get_run_findings(self, run_id: str) -> WorkflowFindings:
        """Get findings from a completed workflow run."""
        url = urljoin(self.base_url, f"/runs/{run_id}/findings")
        response = self._client.get(url)
        data = self._handle_response(response)
        return WorkflowFindings(**data)

    async def aget_run_findings(self, run_id: str) -> WorkflowFindings:
        """Get findings from a completed workflow run (async)."""
        url = urljoin(self.base_url, f"/runs/{run_id}/findings")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return WorkflowFindings(**data)

    def get_workflow_findings(self, workflow_name: str, run_id: str) -> WorkflowFindings:
        """Get findings for a specific workflow run (alternative endpoint)."""
        url = urljoin(self.base_url, f"/runs/{workflow_name}/findings/{run_id}")
        response = self._client.get(url)
        data = self._handle_response(response)
        return WorkflowFindings(**data)

    async def aget_workflow_findings(self, workflow_name: str, run_id: str) -> WorkflowFindings:
        """Get findings for a specific workflow run (alternative endpoint, async)."""
        url = urljoin(self.base_url, f"/runs/{workflow_name}/findings/{run_id}")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return WorkflowFindings(**data)

    # Fuzzing methods

    def get_fuzzing_stats(self, run_id: str) -> FuzzingStats:
        """Get current fuzzing statistics for a run."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}/stats")
        response = self._client.get(url)
        data = self._handle_response(response)
        return FuzzingStats(**data)

    async def aget_fuzzing_stats(self, run_id: str) -> FuzzingStats:
        """Get current fuzzing statistics for a run (async)."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}/stats")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return FuzzingStats(**data)

    def get_crash_reports(self, run_id: str) -> List[CrashReport]:
        """Get crash reports for a fuzzing run."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}/crashes")
        response = self._client.get(url)
        data = self._handle_response(response)
        return [CrashReport(**crash) for crash in data]

    async def aget_crash_reports(self, run_id: str) -> List[CrashReport]:
        """Get crash reports for a fuzzing run (async)."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}/crashes")
        response = await self._async_client.get(url)
        data = await self._ahandle_response(response)
        return [CrashReport(**crash) for crash in data]

    def cleanup_fuzzing_run(self, run_id: str) -> Dict[str, Any]:
        """Clean up fuzzing run data."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}")
        response = self._client.delete(url)
        return self._handle_response(response)

    async def acleanup_fuzzing_run(self, run_id: str) -> Dict[str, Any]:
        """Clean up fuzzing run data (async)."""
        url = urljoin(self.base_url, f"/fuzzing/{run_id}")
        response = await self._async_client.delete(url)
        return await self._ahandle_response(response)

    # Real-time monitoring methods

    async def monitor_fuzzing_websocket(self, run_id: str) -> AsyncIterator[WebSocketMessage]:
        """
        Monitor fuzzing progress via WebSocket for real-time updates.

        Args:
            run_id: The fuzzing run ID to monitor

        Yields:
            WebSocketMessage objects with real-time updates

        Raises:
            WebSocketError: If WebSocket connection fails
        """
        url = f"{self._ws_base_url}/fuzzing/{run_id}/live"

        try:
            async with websockets.connect(
                url,
                timeout=self.timeout,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:
                while True:
                    try:
                        # Send periodic ping to keep connection alive
                        await websocket.ping()

                        # Receive message with timeout
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=self.timeout
                        )

                        if message == "pong":
                            continue

                        data = json.loads(message)
                        yield WebSocketMessage(**data)

                    except asyncio.TimeoutError:
                        logger.warning(f"WebSocket timeout for run {run_id}")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from WebSocket: {e}")
                        continue

        except websockets.exceptions.WebSocketException as e:
            raise WebSocketError(f"WebSocket connection failed: {e}")
        except Exception as e:
            raise WebSocketError(f"WebSocket error: {e}")

    def monitor_fuzzing_sse(self, run_id: str) -> Iterator[SSEMessage]:
        """
        Monitor fuzzing progress via Server-Sent Events.

        Args:
            run_id: The fuzzing run ID to monitor

        Yields:
            SSEMessage objects with real-time updates

        Raises:
            SSEError: If SSE connection fails
        """
        url = urljoin(self.base_url, f"/fuzzing/{run_id}/stream")

        # Prefer requests+sseclient if requests is available; otherwise manually parse SSE via httpx
        if _HAVE_REQUESTS:
            try:
                with requests.Session() as sess:
                    with sess.get(
                        url,
                        headers={"Accept": "text/event-stream"},
                        stream=True,
                        timeout=None,
                    ) as resp:
                        resp.raise_for_status()
                        client = SSEClient(resp)
                        for event in client.events():
                            if not event.data:
                                continue
                            try:
                                data = json.loads(event.data)
                                yield SSEMessage(**data)
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON from SSE: {e}")
                                continue
            except requests.HTTPError as e:  # type: ignore[attr-defined]
                status = getattr(e.response, 'status_code', 0)
                url_txt = getattr(e.request, 'url', url)
                raise from_http_error(status, str(e), str(url_txt))
            except Exception as e:  # pragma: no cover
                raise SSEError(f"SSE connection failed: {e}")
        else:
            # Manual SSE parse over httpx streaming
            try:
                with self._client.stream("GET", url, headers={"Accept": "text/event-stream"}, timeout=None) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    for raw_line in resp.iter_lines():
                        # httpx delivers bytes or str depending on backend; coerce to str
                        line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line)
                        if line == "":
                            # End of event
                            if buffer:
                                try:
                                    data = json.loads(buffer)
                                    yield SSEMessage(**data)
                                except json.JSONDecodeError:
                                    pass
                                buffer = ""
                            continue
                        if line.startswith(":"):
                            # Comment/heartbeat
                            continue
                        if line.startswith("data:"):
                            payload = line[5:].lstrip()
                            # Accumulate multi-line data fields
                            if buffer:
                                buffer += payload
                            else:
                                buffer = payload
            except httpx.HTTPStatusError as e:
                raise from_http_error(e.response.status_code, e.response.text, str(e.request.url))
            except Exception as e:  # pragma: no cover
                raise SSEError(f"SSE error: {e}")

    # Utility methods

    def wait_for_completion(
        self,
        run_id: str,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None
    ) -> WorkflowStatus:
        """
        Wait for a workflow run to complete.

        Args:
            run_id: The run ID to monitor
            poll_interval: How often to check status (seconds)
            timeout: Maximum time to wait (seconds), None for no timeout

        Returns:
            Final WorkflowStatus when completed

        Raises:
            TimeoutError: If timeout is reached
            FuzzForgeHTTPError: If run fails or other API errors
        """
        import time
        start_time = time.time()

        while True:
            status = self.get_run_status(run_id)

            if status.is_completed:
                return status
            elif status.is_failed:
                raise FuzzForgeHTTPError(
                    f"Run {run_id} failed with status: {status.status}",
                    500,
                    details={"run_id": run_id, "status": status.status}
                )

            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Timeout waiting for run {run_id} to complete")

            time.sleep(poll_interval)

    async def await_for_completion(
        self,
        run_id: str,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None
    ) -> WorkflowStatus:
        """
        Wait for a workflow run to complete (async).

        Args:
            run_id: The run ID to monitor
            poll_interval: How often to check status (seconds)
            timeout: Maximum time to wait (seconds), None for no timeout

        Returns:
            Final WorkflowStatus when completed

        Raises:
            TimeoutError: If timeout is reached
            FuzzForgeHTTPError: If run fails or other API errors
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            status = await self.aget_run_status(run_id)

            if status.is_completed:
                return status
            elif status.is_failed:
                raise FuzzForgeHTTPError(
                    f"Run {run_id} failed with status: {status.status}",
                    500,
                    details={"run_id": run_id, "status": status.status}
                )

            # Check timeout
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise TimeoutError(f"Timeout waiting for run {run_id} to complete")

            await asyncio.sleep(poll_interval)
