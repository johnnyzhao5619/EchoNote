"""音频捕获模块

使用 PyAudio 实现音频输入源枚举和实时音频捕获"""

import importlib
import logging
from typing import List, Dict, Optional, Callable
import numpy as np
import threading
import queue

logger = logging.getLogger(__name__)


class AudioCapture:
    """音频捕获器"""

    def __init__(self, sample_rate: int = 16000, channels: int = 1,
                 chunk_size: int = 512, gain: float = 1.0):
        """初始化音频捕获器。

        PyAudio 模块仅在需要时导入和初始化，避免在应用启动时
        强制加载可选依赖。

        Args:
            sample_rate: 采样率（Hz），默认 16000（Whisper 标准）
            channels: 声道数，默认 1（单声道）
            chunk_size: 缓冲区大小（样本数），默认 512（约 32ms @ 16kHz）
            gain: 增益倍数，默认 1.0
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.gain = gain

        self.pyaudio = None
        self.stream = None
        self.is_capturing = False
        self.capture_thread = None
        self.audio_queue = queue.Queue()

        self._pyaudio_module = None
        self._pyaudio_error: Optional[Exception] = None

        # 验证依赖是否存在（不创建实例，避免提前加载底层库）
        self._ensure_module_available()

        logger.info(
            "Audio capture configured: sample_rate=%s, channels=%s, chunk_size=%s. "
            "PyAudio instance will be created on first use.",
            sample_rate,
            channels,
            chunk_size,
        )

    def _ensure_module_available(self):
        """确保可以导入 PyAudio 模块。"""
        if self._pyaudio_module is not None:
            return self._pyaudio_module

        try:
            self._pyaudio_module = importlib.import_module("pyaudio")
            return self._pyaudio_module
        except ImportError as exc:
            self._pyaudio_error = exc
            logger.warning(
                "PyAudio module not found; microphone capture is disabled until installation."
            )
            raise ImportError(
                "PyAudio is not installed. Please install it with: pip install pyaudio"
            ) from exc

    def _ensure_pyaudio_instance(self):
        """按需初始化 PyAudio 实例。"""
        if self.pyaudio is not None:
            return self.pyaudio

        if self._pyaudio_error is not None:
            raise self._pyaudio_error

        try:
            pyaudio_module = self._ensure_module_available()
            self.pyaudio = pyaudio_module.PyAudio()
            logger.info("PyAudio initialized successfully")
        except Exception as exc:  # noqa: BLE001
            self._pyaudio_error = exc
            logger.error("Failed to initialize PyAudio: %s", exc)
            raise

        return self.pyaudio

    def get_input_devices(self) -> List[Dict]:
        """
        枚举所有可用的音频输入设备
        
        Returns:
            List[Dict]: 输入设备列表
            [
                {
                    "index": int,
                    "name": str,
                    "max_input_channels": int,
                    "default_sample_rate": float
                },
                ...
            ]
        """
        try:
            pyaudio_instance = self._ensure_pyaudio_instance()
        except ImportError:
            logger.warning("PyAudio not installed; audio input listing unavailable")
            return []
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to access audio input devices: %s", exc)
            return []

        devices = []
        device_count = pyaudio_instance.get_device_count()

        for i in range(device_count):
            try:
                device_info = pyaudio_instance.get_device_info_by_index(i)
                
                # 只返回输入设备
                if device_info.get('maxInputChannels', 0) > 0:
                    devices.append({
                        "index": i,
                        "name": device_info.get('name', 'Unknown'),
                        "max_input_channels": device_info.get('maxInputChannels', 0),
                        "default_sample_rate": device_info.get('defaultSampleRate', 0)
                    })
            except Exception as e:
                logger.warning(f"Failed to get info for device {i}: {e}")
        
        logger.info(f"Found {len(devices)} input devices")
        return devices

    def list_input_devices(self) -> list:
        """
        列出所有可用的音频输入设备（别名方法，保持 API 一致性）
        
        Returns:
            list: 输入设备列表
        """
        return self.get_input_devices()

    def get_default_input_device(self) -> Optional[Dict]:
        """
        获取默认输入设备
        
        Returns:
            Optional[Dict]: 默认输入设备信息，如果没有则返回 None
        """
        try:
            pyaudio_instance = self._ensure_pyaudio_instance()
            device_info = pyaudio_instance.get_default_input_device_info()
            return {
                "index": device_info.get('index', 0),
                "name": device_info.get('name', 'Unknown'),
                "max_input_channels": device_info.get('maxInputChannels', 0),
                "default_sample_rate": device_info.get('defaultSampleRate', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get default input device: {e}")
            return None

    def start_capture(self, device_index: Optional[int] = None, 
                     callback: Optional[Callable[[np.ndarray], None]] = None):
        """
        开始音频捕获
        
        Args:
            device_index: 输入设备索引（None 表示使用默认设备）
            callback: 音频数据回调函数，接收 numpy array 参数
        """
        if self.is_capturing:
            logger.warning("Audio capture is already running")
            return
        
        pyaudio_instance = self._ensure_pyaudio_instance()
        pyaudio_module = self._ensure_module_available()

        try:
            # 打开音频流
            self.stream = pyaudio_instance.open(
                format=pyaudio_module.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=None  # 使用阻塞模式
            )
            
            self.is_capturing = True
            
            # 启动捕获线程
            self.capture_thread = threading.Thread(
                target=self._capture_loop,
                args=(callback,),
                daemon=True
            )
            self.capture_thread.start()
            
            logger.info(f"Audio capture started (device_index={device_index})")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise

    def _capture_loop(self, callback: Optional[Callable[[np.ndarray], None]]):
        """音频捕获循环（在独立线程中运行）"""
        logger.info("Audio capture loop started")
        
        while self.is_capturing:
            try:
                # 读取音频数据
                audio_data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # 转换为 numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # 转换为 float32 并归一化到 [-1, 1]
                audio_float = audio_array.astype(np.float32) / 32768.0
                
                # 应用增益
                audio_float = audio_float * self.gain
                
                # 限制幅度到 [-1, 1]
                audio_float = np.clip(audio_float, -1.0, 1.0)
                
                # 放入队列
                self.audio_queue.put(audio_float)
                
                # 调用回调函数
                if callback:
                    callback(audio_float)
                    
            except Exception as e:
                if self.is_capturing:
                    logger.error(f"Error in capture loop: {e}")
        
        logger.info("Audio capture loop stopped")

    def stop_capture(self):
        """停止音频捕获"""
        if not self.is_capturing:
            logger.warning("Audio capture is not running")
            return
        
        logger.info("Stopping audio capture...")
        self.is_capturing = False
        
        # 等待捕获线程结束
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        
        # 关闭音频流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        logger.info("Audio capture stopped")

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        从队列中获取音频数据块
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            Optional[np.ndarray]: 音频数据，如果超时则返回 None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def set_gain(self, gain: float):
        """
        设置增益
        
        Args:
            gain: 增益倍数（0.0 - 10.0）
        """
        if gain < 0.0 or gain > 10.0:
            logger.warning(f"Gain value {gain} is out of range [0.0, 10.0]")
            gain = np.clip(gain, 0.0, 10.0)
        
        self.gain = gain
        logger.info(f"Gain set to {gain}")

    def get_volume_level(self) -> float:
        """
        获取当前音量级别（RMS）
        
        Returns:
            float: 音量级别（0.0 - 1.0）
        """
        if self.audio_queue.empty():
            return 0.0
        
        try:
            # 获取最新的音频块（不阻塞）
            audio_chunk = self.audio_queue.get_nowait()
            
            # 计算 RMS（均方根）
            rms = np.sqrt(np.mean(audio_chunk ** 2))
            
            # 放回队列
            self.audio_queue.put(audio_chunk)
            
            return float(rms)
            
        except queue.Empty:
            return 0.0

    def close(self):
        """关闭音频捕获器并释放资源"""
        logger.info("Closing audio capture...")
        
        # 停止捕获
        if self.is_capturing:
            self.stop_capture()
        
        # 终止 PyAudio
        if self.pyaudio:
            self.pyaudio.terminate()
            self.pyaudio = None

        logger.info("Audio capture closed")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
