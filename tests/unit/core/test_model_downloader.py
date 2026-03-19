# SPDX-License-Identifier: Apache-2.0
"""Unit tests for model downloader manifest and auth handling."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from core.models.downloader import ModelDownloader
from core.models.text_ai_registry import TextAIModelInfo


def _build_text_ai_model() -> TextAIModelInfo:
    return TextAIModelInfo(
        model_id="gemma-3-1b-it-gguf",
        display_name="Gemma 3 1B Instruct",
        runtime="gguf",
        provider="llama_cpp",
        description="meeting",
        family="meeting",
        size_mb=770,
        repo_id="ggml-org/gemma-3-1b-it-GGUF",
        required_files=("model.gguf",),
        download_files=(("gemma-3-1b-it-Q4_K_M.gguf", "model.gguf"),),
    )


def test_model_downloader_uses_explicit_remote_to_local_file_mapping(tmp_path):
    downloader = ModelDownloader(tmp_path)
    model = _build_text_ai_model()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "siblings": [
            {"rfilename": "gemma-3-1b-it-Q4_K_M.gguf", "size": 123},
            {"rfilename": "README.md", "size": 456},
        ]
    }

    with patch("core.models.downloader.requests.get", return_value=response):
        files = downloader._fetch_remote_manifest(model)

    assert len(files) == 1
    assert files[0].remote_path == "gemma-3-1b-it-Q4_K_M.gguf"
    assert files[0].local_path == "model.gguf"
    assert files[0].size == 123


def test_model_downloader_reports_private_or_authenticated_manifests(tmp_path):
    downloader = ModelDownloader(tmp_path)
    model = _build_text_ai_model()
    response = Mock()
    response.status_code = 401
    response.raise_for_status.side_effect = requests.HTTPError("401 unauthorized")

    with patch("core.models.downloader.requests.get", return_value=response):
        with pytest.raises(PermissionError, match="requires authentication"):
            downloader._fetch_remote_manifest(model)
