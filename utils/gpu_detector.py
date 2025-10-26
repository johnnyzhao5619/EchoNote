# SPDX-License-Identifier: Apache-2.0
#
# Copyright (c) 2024-2025 EchoNote Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
GPU detection utility for EchoNote.

Detects available compute devices (CPU, CUDA, CoreML) for faster-whisper.
"""

import logging
import platform
from typing import Dict, List, Tuple


logger = logging.getLogger(__name__)


class GPUDetector:
    """Detects available GPU and compute devices."""

    @staticmethod
    def detect_available_devices() -> Dict[str, bool]:
        """
        Detect available compute devices.

        Returns:
            Dict with device availability:
            {
                'cpu': True,
                'cuda': bool,
                'coreml': bool
            }
        """
        devices = {
            'cpu': True,  # CPU is always available
            'cuda': False,
            'coreml': False
        }

        # Check CUDA availability
        try:
            import torch
            if torch.cuda.is_available():
                devices['cuda'] = True
                cuda_device_count = torch.cuda.device_count()
                logger.info(
                    f"CUDA is available with {cuda_device_count} device(s)"
                )

                # Log GPU details
                for i in range(cuda_device_count):
                    gpu_name = torch.cuda.get_device_name(i)
                    logger.info(f"  GPU {i}: {gpu_name}")
            else:
                logger.info("CUDA is not available")
        except ImportError:
            logger.warning(
                "torch is not installed, CUDA detection skipped"
            )
        except Exception as e:
            logger.warning(f"Error detecting CUDA: {e}")

        # Check CoreML availability (Apple Silicon)
        try:
            processor = platform.processor()
            system = platform.system()

            # CoreML is available on Apple Silicon (arm64)
            if system == 'Darwin' and processor == 'arm':
                devices['coreml'] = True
                logger.info(
                    "CoreML is available (Apple Silicon detected)"
                )
            else:
                logger.info(
                    f"CoreML not available "
                    f"(system={system}, processor={processor})"
                )
        except Exception as e:
            logger.warning(f"Error detecting CoreML: {e}")

        return devices

    @staticmethod
    def get_recommended_device() -> Tuple[str, str]:
        """
        Get recommended device and compute type.

        Returns:
            Tuple of (device, compute_type)
            - device: 'cuda', 'cpu'
            - compute_type: 'float16', 'int8', 'float32'
        """
        devices = GPUDetector.detect_available_devices()

        # Priority: CUDA > CoreML > CPU
        if devices['cuda']:
            # CUDA with float16 for best performance
            logger.info("Recommending CUDA with float16")
            return ('cuda', 'float16')
        elif devices['coreml']:
            # CoreML optimization is automatic in faster-whisper
            # on Apple Silicon
            # Use CPU device with int8 (CoreML will be used internally)
            logger.info(
                "Recommending CPU with int8 "
                "(CoreML will be used automatically)"
            )
            return ('cpu', 'int8')
        else:
            # CPU with int8 for best CPU performance
            logger.info("Recommending CPU with int8")
            return ('cpu', 'int8')

    @staticmethod
    def get_device_display_name(device: str) -> str:
        """
        Get user-friendly display name for device.

        Args:
            device: Device identifier ('cpu', 'cuda', 'auto')

        Returns:
            Display name
        """
        display_names = {
            'cpu': 'CPU',
            'cuda': 'CUDA (NVIDIA GPU)',
            'auto': 'Auto (Recommended)'
        }
        return display_names.get(device, device.upper())

    @staticmethod
    def validate_device_config(
        device: str,
        compute_type: str
    ) -> Tuple[str, str, str]:
        """
        Validate and adjust device configuration.

        Args:
            device: Requested device ('cpu', 'cuda', 'auto')
            compute_type: Requested compute type

        Returns:
            Tuple of (actual_device, actual_compute_type, warning_message)
            warning_message is empty string if no issues
        """
        devices = GPUDetector.detect_available_devices()
        warning = ""

        # Handle 'auto' device
        if device == 'auto':
            device, compute_type = GPUDetector.get_recommended_device()
            logger.info(
                f"Auto-selected device: {device}, "
                f"compute_type: {compute_type}"
            )
            return (device, compute_type, "")

        # Validate CUDA request
        if device == 'cuda':
            if not devices['cuda']:
                # CUDA not available, fallback to CPU
                warning = "CUDA is not available. Falling back to CPU."
                logger.warning(warning)
                device = 'cpu'
                compute_type = 'int8'
            else:
                # CUDA available, ensure compatible compute type
                if compute_type not in ['float16', 'float32']:
                    logger.info(
                        f"Adjusting compute_type from {compute_type} "
                        f"to float16 for CUDA"
                    )
                    compute_type = 'float16'

        # Validate CPU request
        if device == 'cpu':
            # CPU works with any compute type, but int8 is recommended
            if compute_type not in ['int8', 'float16', 'float32']:
                logger.info(
                    f"Invalid compute_type {compute_type}, using int8"
                )
                compute_type = 'int8'

        return (device, compute_type, warning)

    @staticmethod
    def get_available_device_options() -> List[Tuple[str, str]]:
        """
        Get list of available device options for UI.

        Returns:
            List of (device_id, display_name) tuples
        """
        devices = GPUDetector.detect_available_devices()
        options = [('auto', 'Auto (Recommended)')]

        # CPU is always available
        options.append(('cpu', 'CPU'))

        # Add CUDA if available
        if devices['cuda']:
            try:
                import torch
                gpu_name = torch.cuda.get_device_name(0)
                options.append(('cuda', f'CUDA ({gpu_name})'))
            except Exception:
                options.append(('cuda', 'CUDA (NVIDIA GPU)'))

        return options
