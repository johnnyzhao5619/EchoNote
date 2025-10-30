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
音频波形可视化组件

实现实时音频波形和音量表显示
"""

import logging
from collections import deque

import numpy as np
from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QColor, QPainter, QPen

from ui.base_widgets import BaseWidget

logger = logging.getLogger(__name__)


class AudioVisualizer(BaseWidget):
    """音频波形可视化组件"""

    def __init__(self, parent=None, i18n=None):
        """
        初始化音频可视化组件

        Args:
            parent: 父窗口
            i18n: 国际化管理器
        """
        super().__init__(i18n, parent)
        self.i18n = i18n

        # 波形数据缓冲区（保存最近的音频样本）
        self.waveform_buffer = deque(maxlen=1000)

        # 音量级别（RMS）
        self.volume_level = 0.0

        # 设置最小尺寸
        self.setMinimumHeight(100)
        self.setMinimumWidth(400)

        # 刷新定时器（30 FPS）
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update)
        self.refresh_timer.start(33)  # 约 30 FPS

        # 颜色配置
        self.waveform_color = QColor(33, 150, 243)  # 蓝色
        self.volume_bar_color = QColor(76, 175, 80)  # 绿色
        self.volume_bar_high_color = QColor(255, 152, 0)  # 橙色
        self.volume_bar_peak_color = QColor(244, 67, 54)  # 红色
        self.background_color = QColor(250, 250, 250)
        self.grid_color = QColor(220, 220, 220)

        if self.i18n:
            logger.info(self.i18n.t("logging.audio_visualizer.initialized"))
        else:
            logger.info("AudioVisualizer initialized")

    def update_audio_data(self, audio_chunk: np.ndarray):
        """
        更新音频数据

        Args:
            audio_chunk: 音频数据块（numpy array）
        """
        if audio_chunk is None or len(audio_chunk) == 0:
            return

        # 计算 RMS（均方根）音量
        rms = np.sqrt(np.mean(audio_chunk**2))
        self.volume_level = float(rms)

        # 下采样音频数据用于波形显示
        # 如果数据太多，取平均值
        if len(audio_chunk) > 100:
            # 将数据分成 100 段，每段取平均值
            chunk_size = len(audio_chunk) // 100
            downsampled = []
            for i in range(0, len(audio_chunk), chunk_size):
                segment = audio_chunk[i : i + chunk_size]
                if len(segment) > 0:
                    downsampled.append(np.mean(segment))
            audio_chunk = np.array(downsampled)

        # 添加到缓冲区
        for sample in audio_chunk:
            self.waveform_buffer.append(float(sample))

    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景
        painter.fillRect(self.rect(), self.background_color)

        # 计算布局
        width = self.width()
        height = self.height()

        # 波形区域占 80%，音量表占 20%
        waveform_width = int(width * 0.8)
        volume_bar_width = width - waveform_width - 10

        # 绘制波形
        self._draw_waveform(painter, QRect(0, 0, waveform_width, height))

        # 绘制音量表
        self._draw_volume_bar(painter, QRect(waveform_width + 10, 0, volume_bar_width, height))

    def _draw_waveform(self, painter: QPainter, rect: QRect):
        """
        绘制波形

        Args:
            painter: QPainter 实例
            rect: 绘制区域
        """
        if len(self.waveform_buffer) == 0:
            return

        # 绘制网格线
        painter.setPen(QPen(self.grid_color, 1))
        center_y = rect.height() // 2
        painter.drawLine(rect.left(), center_y, rect.right(), center_y)

        # 绘制波形
        painter.setPen(QPen(self.waveform_color, 2))

        # 将缓冲区数据转换为坐标点
        buffer_data = list(self.waveform_buffer)
        num_samples = len(buffer_data)

        if num_samples < 2:
            return

        # 计算 x 轴步长
        x_step = rect.width() / num_samples

        # 绘制波形线
        for i in range(num_samples - 1):
            # 当前样本
            x1 = rect.left() + int(i * x_step)
            y1 = center_y - int(buffer_data[i] * center_y)

            # 下一个样本
            x2 = rect.left() + int((i + 1) * x_step)
            y2 = center_y - int(buffer_data[i + 1] * center_y)

            # 限制 y 坐标在有效范围内
            y1 = max(rect.top(), min(rect.bottom(), y1))
            y2 = max(rect.top(), min(rect.bottom(), y2))

            painter.drawLine(x1, y1, x2, y2)

    def _draw_volume_bar(self, painter: QPainter, rect: QRect):
        """
        绘制音量表

        Args:
            painter: QPainter 实例
            rect: 绘制区域
        """
        # 绘制边框
        painter.setPen(QPen(self.grid_color, 1))
        painter.drawRect(rect)

        # 计算音量条高度
        bar_height = int(rect.height() * self.volume_level)
        bar_height = min(bar_height, rect.height())

        if bar_height <= 0:
            return

        # 根据音量级别选择颜色
        if self.volume_level > 0.8:
            color = self.volume_bar_peak_color
        elif self.volume_level > 0.5:
            color = self.volume_bar_high_color
        else:
            color = self.volume_bar_color

        # 绘制音量条（从底部向上）
        bar_rect = QRect(rect.left() + 1, rect.bottom() - bar_height, rect.width() - 2, bar_height)
        painter.fillRect(bar_rect, color)

        # 绘制刻度线
        painter.setPen(QPen(self.grid_color, 1))
        for i in range(1, 10):
            y = rect.bottom() - int(rect.height() * i / 10)
            painter.drawLine(rect.left(), y, rect.left() + 5, y)

    def clear(self):
        """清空波形数据"""
        self.waveform_buffer.clear()
        self.volume_level = 0.0
        self.update()

    def set_colors(self, waveform_color=None, volume_bar_color=None, background_color=None):
        """
        设置颜色

        Args:
            waveform_color: 波形颜色
            volume_bar_color: 音量条颜色
            background_color: 背景颜色
        """
        if waveform_color:
            self.waveform_color = waveform_color
        if volume_bar_color:
            self.volume_bar_color = volume_bar_color
        if background_color:
            self.background_color = background_color

    def stop(self):
        """停止刷新"""
        self.refresh_timer.stop()

    def start(self):
        """开始刷新"""
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(33)
