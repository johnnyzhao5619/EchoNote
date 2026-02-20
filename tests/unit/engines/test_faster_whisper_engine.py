# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for FasterWhisperEngine.

Tests model loading, transcription, and configuration.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from engines.speech.faster_whisper_engine import FasterWhisperEngine


@pytest.fixture
def mock_model_manager():
    """Create mock model manager."""
    manager = Mock()

    # Mock model info
    model_info = Mock()
    model_info.name = "base"
    model_info.is_downloaded = True
    model_info.local_path = "/tmp/models/base"

    manager.get_model = Mock(return_value=model_info)
    manager.get_downloaded_models = Mock(return_value=[model_info])
    manager.mark_model_used = Mock()

    return manager


@pytest.fixture
def mock_whisper_model():
    """Create mock WhisperModel."""
    model = Mock()

    # Mock transcribe method
    segment = Mock()
    segment.text = "Test transcription"
    segment.start = 0.0
    segment.end = 1.0

    info = Mock()
    info.language = "en"
    info.duration = 1.0

    model.transcribe = Mock(return_value=([segment], info))

    return model


class TestFasterWhisperEngineInitialization:
    """Test FasterWhisperEngine initialization."""

    def test_init_with_model_manager(self, mock_model_manager):
        """Test initialization with model manager."""
        engine = FasterWhisperEngine(
            model_size="base", device="cpu", compute_type="int8", model_manager=mock_model_manager
        )

        assert engine.model_size == "base"
        assert engine.device == "cpu"
        assert engine.compute_type == "int8"
        assert engine.model_manager == mock_model_manager
        assert engine._model_available

    def test_init_without_model_manager(self):
        """Test initialization without model manager (legacy mode)."""
        engine = FasterWhisperEngine(model_size="base", device="cpu", compute_type="int8")

        assert engine.model_size == "base"
        assert engine.model_manager is None
        assert engine._model_available

    def test_init_with_unavailable_model(self, mock_model_manager):
        """Test initialization when model is not downloaded."""
        # Mock model as not downloaded
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)

        # But has fallback model
        fallback = Mock()
        fallback.name = "tiny"
        fallback.local_path = "/tmp/models/tiny"
        fallback.is_downloaded = True
        mock_model_manager.get_downloaded_models = Mock(return_value=[fallback])

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        # Should use fallback model
        assert engine.model_size == "tiny"
        assert engine._model_available

    def test_init_with_no_models_available(self, mock_model_manager):
        """Test initialization when no models are available."""
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)
        mock_model_manager.get_downloaded_models = Mock(return_value=[])

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        assert not engine._model_available

    @patch("utils.gpu_detector.GPUDetector")
    def test_init_device_validation(self, mock_gpu_detector, mock_model_manager):
        """Test device configuration validation."""
        mock_gpu_detector.validate_device_config = Mock(
            return_value=("cpu", "int8", "GPU not available")
        )

        engine = FasterWhisperEngine(
            model_size="base", device="cuda", model_manager=mock_model_manager
        )

        # Should fall back to CPU
        assert engine.device == "cpu"
        assert engine.compute_type == "int8"


class TestModelAvailability:
    """Test model availability checking."""

    def test_is_model_available_true(self, mock_model_manager):
        """Test checking model availability when model is available."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        assert engine.is_model_available()

    def test_is_model_available_false(self, mock_model_manager):
        """Test checking model availability when model is not available."""
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)
        mock_model_manager.get_downloaded_models = Mock(return_value=[])

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        assert not engine.is_model_available()

    def test_refresh_model_status(self, mock_model_manager):
        """Test refreshing model status."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        # Initially available
        assert engine._model_available

        # Change model status
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)

        # Refresh status
        engine._refresh_model_status()

        assert not engine._model_available


class TestEngineInterface:
    """Test engine interface methods."""

    def test_get_name(self, mock_model_manager):
        """Test getting engine name."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        assert engine.get_name() == "faster-whisper-base"

    def test_get_supported_languages(self, mock_model_manager):
        """Test getting supported languages."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        languages = engine.get_supported_languages()

        assert isinstance(languages, list)
        assert len(languages) > 0
        assert "en" in languages
        assert "zh" in languages

    def test_get_config_schema(self, mock_model_manager):
        """Test getting configuration schema."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        schema = engine.get_config_schema()

        assert isinstance(schema, dict)
        assert "type" in schema
        assert "properties" in schema


class TestModelLoading:
    """Test model loading functionality."""

    @patch("faster_whisper.WhisperModel")
    def test_load_model_success(self, mock_whisper_class, mock_model_manager):
        """Test successful model loading."""
        mock_whisper_class.return_value = Mock()

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        engine._load_model()

        assert engine.model is not None
        mock_whisper_class.assert_called_once()

    def test_load_model_unavailable(self, mock_model_manager):
        """Test loading model when not available."""
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)
        mock_model_manager.get_downloaded_models = Mock(return_value=[])

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        with pytest.raises(ValueError, match="No speech recognition models"):
            engine._load_model()

    @patch("faster_whisper.WhisperModel")
    def test_load_model_already_loaded(self, mock_whisper_class, mock_model_manager):
        """Test that model is not reloaded if already loaded."""
        mock_whisper_class.return_value = Mock()

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        engine._load_model()
        first_model = engine.model

        # Load again
        engine._load_model()

        # Should be same instance
        assert engine.model is first_model
        # Should only be called once
        assert mock_whisper_class.call_count == 1

    @patch("faster_whisper.WhisperModel")
    def test_load_model_cuda_fallback(self, mock_whisper_class, mock_model_manager):
        """Test CUDA fallback to CPU."""
        # First call raises CUDA error, second succeeds
        mock_whisper_class.side_effect = [ValueError("CUDA not available"), Mock()]

        engine = FasterWhisperEngine(
            model_size="base", device="cuda", model_manager=mock_model_manager
        )

        engine._load_model()

        # Should fall back to CPU
        assert engine.device == "cpu"
        assert engine.compute_type == "int8"
        assert engine.model is not None


class TestModelUsageTracking:
    """Test model usage tracking."""

    def test_record_model_usage(self, mock_model_manager):
        """Test recording model usage."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        engine._record_model_usage()

        mock_model_manager.mark_model_used.assert_called_once_with("base")

    def test_record_model_usage_no_manager(self):
        """Test recording model usage without manager."""
        engine = FasterWhisperEngine(model_size="base")

        # Should not raise error
        engine._record_model_usage()

    def test_record_model_usage_error_handling(self, mock_model_manager):
        """Test error handling in model usage recording."""
        mock_model_manager.mark_model_used = Mock(side_effect=RuntimeError("Database error"))

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        # Should not raise error, just log warning
        engine._record_model_usage()


class TestTranscribeFile:
    """Test file transcription."""

    @pytest.mark.asyncio
    @patch("faster_whisper.WhisperModel")
    @patch("soundfile.info")
    async def test_transcribe_file_basic(
        self, mock_sf_info, mock_whisper_class, mock_model_manager
    ):
        """Test basic file transcription."""
        # Mock soundfile info
        info = Mock()
        info.duration = 10.0
        mock_sf_info.return_value = info

        # Mock WhisperModel
        segment = Mock()
        segment.text = "Test transcription"
        segment.start = 0.0
        segment.end = 10.0

        transcribe_info = Mock()
        transcribe_info.language = "en"
        transcribe_info.duration = 10.0

        mock_model = Mock()
        mock_model.transcribe = Mock(return_value=([segment], transcribe_info))
        mock_whisper_class.return_value = mock_model

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        result = await engine.transcribe_file("/tmp/test.wav", language="en")

        assert "segments" in result
        assert "language" in result
        assert "duration" in result
        assert result["language"] == "en"
        assert len(result["segments"]) > 0

    @pytest.mark.asyncio
    @patch("faster_whisper.WhisperModel")
    @patch("subprocess.run")
    @patch("soundfile.info")
    async def test_transcribe_file_mp4_prefers_ffprobe_duration_probe(
        self,
        mock_sf_info,
        mock_subprocess_run,
        mock_whisper_class,
        mock_model_manager,
    ):
        """MP4 should prefer ffprobe duration probing and avoid noisy soundfile probe errors."""
        mock_sf_info.side_effect = RuntimeError("Format not recognised")
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout='{"format": {"duration": "12.5"}}',
            stderr="",
        )

        segment = Mock()
        segment.text = "Test transcription"
        segment.start = 0.0
        segment.end = 10.0

        transcribe_info = Mock()
        transcribe_info.language = "en"
        transcribe_info.duration = 10.0

        mock_model = Mock()
        mock_model.transcribe = Mock(return_value=([segment], transcribe_info))
        mock_whisper_class.return_value = mock_model

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)
        result = await engine.transcribe_file("/tmp/test.mp4", language="en")

        assert result["duration"] == pytest.approx(12.5)
        mock_subprocess_run.assert_called_once()
        mock_sf_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_transcribe_file_model_unavailable(self, mock_model_manager):
        """Test transcription when model is unavailable."""
        model_info = Mock()
        model_info.is_downloaded = False
        mock_model_manager.get_model = Mock(return_value=model_info)
        mock_model_manager.get_downloaded_models = Mock(return_value=[])

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        with pytest.raises(ValueError, match="No speech recognition models"):
            await engine.transcribe_file("/tmp/test.wav")


class TestTranscribeStream:
    """Test stream transcription."""

    @pytest.mark.asyncio
    @patch("faster_whisper.WhisperModel")
    async def test_transcribe_stream_basic(self, mock_whisper_class, mock_model_manager):
        """Test basic stream transcription."""
        mock_model = Mock()
        segment = Mock()
        segment.text = "Test transcription"
        info = Mock()
        info.language = "en"
        mock_model.transcribe = Mock(return_value=([segment], info))
        mock_whisper_class.return_value = mock_model

        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        # Create audio chunk
        audio_chunk = np.random.rand(16000).astype(np.float32)

        result = await engine.transcribe_stream(audio_chunk, language="en", sample_rate=16000)

        assert isinstance(result, dict)
        assert "text" in result
        assert "language" in result
        assert result["language"] == "en"


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_valid(self, mock_model_manager):
        """Test validating valid configuration."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        config = {"model_size": "base", "device": "cpu", "compute_type": "int8"}

        assert engine.validate_config(config)

    def test_validate_config_missing_required(self, mock_model_manager):
        """Test validating configuration with missing required fields."""
        engine = FasterWhisperEngine(model_size="base", model_manager=mock_model_manager)

        config = {}

        # Should still validate (base implementation is lenient)
        result = engine.validate_config(config)
        assert isinstance(result, bool)
