"""
音频缓冲区模块

实现音频数据缓存和滑动窗口访问，用于实时转录
"""

import logging
from typing import Optional
import numpy as np
from collections import deque
import threading

logger = logging.getLogger(__name__)


class AudioBuffer:
    """音频缓冲区，支持滑动窗口访问"""

    def __init__(self, max_duration_seconds: int = 60, sample_rate: int = 16000):
        """
        初始化音频缓冲区
        
        Args:
            max_duration_seconds: 最大缓冲时长（秒）
            sample_rate: 采样率（Hz）
        """
        self.max_duration_seconds = max_duration_seconds
        self.sample_rate = sample_rate
        self.max_samples = max_duration_seconds * sample_rate
        
        # 使用 deque 实现固定大小的环形缓冲区
        self.buffer = deque(maxlen=self.max_samples)
        
        # 线程锁，确保线程安全
        self.lock = threading.Lock()
        
        # 统计信息
        self.total_samples_added = 0
        
        logger.info(f"Audio buffer initialized: max_duration={max_duration_seconds}s, sample_rate={sample_rate}Hz")

    def append(self, audio_chunk: np.ndarray):
        """
        添加音频数据块到缓冲区
        
        Args:
            audio_chunk: 音频数据（numpy array）
        """
        with self.lock:
            # 将音频块的每个样本添加到 deque
            for sample in audio_chunk:
                self.buffer.append(sample)
            
            self.total_samples_added += len(audio_chunk)
            
            logger.debug(f"Added {len(audio_chunk)} samples to buffer (total: {len(self.buffer)})")

    def get_window(self, duration_seconds: float, offset_seconds: float = 0.0) -> np.ndarray:
        """
        获取指定时长的音频窗口
        
        Args:
            duration_seconds: 窗口时长（秒）
            offset_seconds: 偏移量（秒），0 表示最新数据，正值表示向过去偏移
            
        Returns:
            np.ndarray: 音频数据窗口
        """
        with self.lock:
            buffer_size = len(self.buffer)
            
            if buffer_size == 0:
                return np.array([], dtype=np.float32)
            
            # 计算样本数
            window_samples = int(duration_seconds * self.sample_rate)
            offset_samples = int(offset_seconds * self.sample_rate)
            
            # 计算窗口的起始和结束位置
            end_pos = buffer_size - offset_samples
            start_pos = max(0, end_pos - window_samples)
            
            # 确保位置有效
            if start_pos >= buffer_size or end_pos <= 0:
                return np.array([], dtype=np.float32)
            
            end_pos = min(end_pos, buffer_size)
            
            # 提取窗口数据
            window_data = list(self.buffer)[start_pos:end_pos]
            
            logger.debug(f"Retrieved window: duration={duration_seconds}s, offset={offset_seconds}s, samples={len(window_data)}")
            
            return np.array(window_data, dtype=np.float32)

    def get_latest(self, duration_seconds: float) -> np.ndarray:
        """
        获取最新的指定时长的音频数据
        
        Args:
            duration_seconds: 时长（秒）
            
        Returns:
            np.ndarray: 最新的音频数据
        """
        return self.get_window(duration_seconds, offset_seconds=0.0)

    def get_all(self) -> np.ndarray:
        """
        获取缓冲区中的所有音频数据
        
        Returns:
            np.ndarray: 所有音频数据
        """
        with self.lock:
            if len(self.buffer) == 0:
                return np.array([], dtype=np.float32)
            
            return np.array(list(self.buffer), dtype=np.float32)

    def get_sliding_windows(self, window_duration_seconds: float, 
                           overlap_seconds: float = 0.0) -> list:
        """
        获取滑动窗口列表
        
        Args:
            window_duration_seconds: 窗口时长（秒）
            overlap_seconds: 重叠时长（秒）
            
        Returns:
            list: 窗口列表，每个窗口是一个 numpy array
        """
        with self.lock:
            buffer_size = len(self.buffer)
            
            if buffer_size == 0:
                return []
            
            window_samples = int(window_duration_seconds * self.sample_rate)
            step_samples = int((window_duration_seconds - overlap_seconds) * self.sample_rate)
            
            if step_samples <= 0:
                logger.warning("Invalid overlap: overlap must be less than window duration")
                return []
            
            windows = []
            buffer_list = list(self.buffer)
            
            for start_pos in range(0, buffer_size - window_samples + 1, step_samples):
                end_pos = start_pos + window_samples
                window_data = buffer_list[start_pos:end_pos]
                windows.append(np.array(window_data, dtype=np.float32))
            
            logger.debug(f"Generated {len(windows)} sliding windows")
            return windows

    def clear(self):
        """清空缓冲区"""
        with self.lock:
            self.buffer.clear()
            self.total_samples_added = 0
            logger.info("Audio buffer cleared")

    def get_duration(self) -> float:
        """
        获取缓冲区中音频的总时长
        
        Returns:
            float: 时长（秒）
        """
        with self.lock:
            return len(self.buffer) / self.sample_rate

    def get_size(self) -> int:
        """
        获取缓冲区中的样本数
        
        Returns:
            int: 样本数
        """
        with self.lock:
            return len(self.buffer)

    def is_empty(self) -> bool:
        """
        检查缓冲区是否为空
        
        Returns:
            bool: 是否为空
        """
        with self.lock:
            return len(self.buffer) == 0

    def is_full(self) -> bool:
        """
        检查缓冲区是否已满
        
        Returns:
            bool: 是否已满
        """
        with self.lock:
            return len(self.buffer) >= self.max_samples

    def get_memory_usage(self) -> int:
        """
        获取缓冲区的内存使用量
        
        Returns:
            int: 内存使用量（字节）
        """
        with self.lock:
            # 每个 float32 样本占用 4 字节
            return len(self.buffer) * 4

    def get_stats(self) -> dict:
        """
        获取缓冲区统计信息
        
        Returns:
            dict: 统计信息
        """
        with self.lock:
            return {
                "current_samples": len(self.buffer),
                "max_samples": self.max_samples,
                "current_duration_seconds": len(self.buffer) / self.sample_rate,
                "max_duration_seconds": self.max_duration_seconds,
                "total_samples_added": self.total_samples_added,
                "memory_usage_bytes": len(self.buffer) * 4,
                "is_full": len(self.buffer) >= self.max_samples,
                "fill_percentage": (len(self.buffer) / self.max_samples) * 100
            }
