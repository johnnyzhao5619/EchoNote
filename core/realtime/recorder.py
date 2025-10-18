"""
实时录制管理器

实现实时音频录制、转录和翻译的完整流程
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, AsyncIterator, Callable
import numpy as np
import soundfile as sf

from core.realtime.audio_buffer import AudioBuffer

logger = logging.getLogger(__name__)


class RealtimeRecorder:
    """实时录制管理器"""

    def __init__(self, audio_capture, speech_engine, translation_engine,
                 db_connection, file_manager):
        """
        初始化实时录制管理器

        Args:
            audio_capture: AudioCapture 实例
            speech_engine: SpeechEngine 实例
            translation_engine: TranslationEngine 实例（可选）
            db_connection: 数据库连接
            file_manager: FileManager 实例
        """
        self.audio_capture = audio_capture
        self.speech_engine = speech_engine
        self.translation_engine = translation_engine
        self.db = db_connection
        self.file_manager = file_manager

        if self.audio_capture is None:
            logger.warning(
                "Audio capture not available. Real-time recording features will remain disabled."
            )

        # 默认采样率
        self.sample_rate = 16000
        if self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, 'sample_rate', None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)

        # 录制状态
        self.is_recording = False
        self.recording_start_time = None
        self.recording_audio_buffer = []
        self.audio_buffer: Optional[AudioBuffer] = None

        # 转录和翻译队列
        self.transcription_queue = asyncio.Queue()
        self.translation_queue = asyncio.Queue()

        # 异步任务
        self.processing_task = None
        self.translation_task = None

        # 录制选项
        self.current_options = {}

        # 回调函数（用于 UI 更新）
        self.on_transcription_update = None
        self.on_translation_update = None
        self.on_error = None
        self.on_audio_data = None  # 音频数据回调（用于可视化等）

        # 累积的转录和翻译文本
        self.accumulated_transcription = []
        self.accumulated_translation = []

        # 事件循环引用（用于线程安全的队列操作）
        self._event_loop = None

        logger.info("RealtimeRecorder initialized")

    def audio_input_available(self) -> bool:
        """实时录音输入是否可用。"""
        return self.audio_capture is not None

    def set_callbacks(
        self,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_translation: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_audio_data: Optional[Callable[[np.ndarray], None]] = None
    ):
        """
        设置回调函数（用于 UI 更新）

        Args:
            on_transcription: 转录文本更新回调
            on_translation: 翻译文本更新回调
            on_error: 错误回调
            on_audio_data: 音频数据回调（用于可视化等）
        """
        self.on_transcription_update = on_transcription
        self.on_translation_update = on_translation
        self.on_error = on_error
        self.on_audio_data = on_audio_data

    async def start_recording(
        self, input_source: Optional[int] = None,
        options: Optional[Dict] = None,
        event_loop=None
    ):
        """
        开始录制

        Args:
            input_source: 音频输入设备索引（None 表示默认设备）
            options: 录制选项
                - language: 源语言代码
                - enable_translation: 是否启用翻译
                - target_language: 目标语言代码
                - recording_format: 录音格式（'wav' 或 'mp3'）
                - save_recording: 是否保存录音文件
                - save_transcript: 是否保存转录文本
                - create_calendar_event: 是否创建日历事件
            event_loop: 事件循环（如果提供，将使用此循环）
        """
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return

        if self.audio_capture is None:
            raise RuntimeError(
                "Audio capture is not available. Install PyAudio to enable real-time recording."
            )

        # 保存事件循环引用（用于线程安全的队列操作）
        if event_loop is not None:
            self._event_loop = event_loop
        else:
            self._event_loop = asyncio.get_event_loop()

        # 保存选项
        self.current_options = options or {}

        # 同步采样率设置（优先使用选项覆盖，其次使用音频采集配置）
        option_rate = self.current_options.get('sample_rate')
        if isinstance(option_rate, (int, float)) and option_rate > 0:
            self.sample_rate = int(option_rate)
        elif self.audio_capture is not None:
            capture_rate = getattr(self.audio_capture, 'sample_rate', None)
            if isinstance(capture_rate, (int, float)) and capture_rate > 0:
                self.sample_rate = int(capture_rate)
        else:
            self.sample_rate = 16000

        # 重置状态
        self.is_recording = True
        self.recording_start_time = datetime.now()
        self.recording_audio_buffer = []
        self.audio_buffer = AudioBuffer(sample_rate=self.sample_rate)
        self.accumulated_transcription = []
        self.accumulated_translation = []

        # 清空队列
        while not self.transcription_queue.empty():
            try:
                self.transcription_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self.translation_queue.empty():
            try:
                self.translation_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 启动音频捕获
        self.audio_capture.start_capture(
            device_index=input_source,
            callback=self._audio_callback
        )

        # 启动异步处理任务
        self.processing_task = asyncio.create_task(
            self._process_audio_stream()
        )

        # 如果启用翻译，启动翻译任务
        if self.current_options.get('enable_translation', False):
            self.translation_task = asyncio.create_task(
                self._process_translation_stream()
            )

        logger.info(f"Recording started (input_source={input_source})")

    def _audio_callback(self, audio_chunk: np.ndarray):
        """
        音频回调函数（在音频捕获线程中调用）

        Args:
            audio_chunk: 音频数据块
        """
        if not self.is_recording:
            return

        # 保存音频数据用于最终保存
        self.recording_audio_buffer.append(audio_chunk.copy())

        # 将音频块放入转录队列（使用线程安全的方式）
        try:
            # 使用 call_soon_threadsafe 来在事件循环中安全地添加任务
            if hasattr(self, '_event_loop') and self._event_loop is not None:
                self._event_loop.call_soon_threadsafe(
                    self.transcription_queue.put_nowait,
                    audio_chunk.copy()
                )
            else:
                logger.debug("Event loop not set, audio chunk not queued")
        except Exception as e:
            logger.warning(f"Failed to queue audio chunk: {e}")

        # 调用音频数据回调（用于可视化等）
        if self.on_audio_data:
            try:
                self.on_audio_data(audio_chunk.copy())
            except Exception as e:
                logger.warning(f"Error in audio data callback: {e}")

    async def _process_audio_stream(self):
        """处理音频流的异步任务"""
        logger.info("Audio stream processing started")

        # 导入 VAD 检测器
        from engines.audio.vad import VADDetector

        # 创建 VAD 检测器和音频缓冲区
        vad = None
        try:
            vad = VADDetector(
                threshold=0.3,  # 降低阈值，更容易检测到语音
                silence_duration_ms=1500,  # 减少静音时长要求
                method='silero'
            )
            logger.info("VAD detector initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize VAD: {e}. Will process all audio without VAD.")
            # 不返回，继续处理但不使用 VAD

        sample_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000

        audio_buffer = self.audio_buffer
        if audio_buffer is None:
            audio_buffer = AudioBuffer(sample_rate=sample_rate)
            self.audio_buffer = audio_buffer

        min_audio_duration = 3.0  # 最小3秒音频才处理

        audio_chunks_received = 0
        transcription_attempts = 0
        last_transcription = ""  # 记录上一次转录结果，用于去重

        while self.is_recording:
            try:
                # 从队列获取音频块（超时 0.5 秒）
                audio_chunk = await asyncio.wait_for(
                    self.transcription_queue.get(),
                    timeout=0.5
                )
                
                audio_chunks_received += 1
                logger.debug(f"Received audio chunk #{audio_chunks_received}, size: {len(audio_chunk)}")

                # 添加到音频缓冲区
                audio_buffer.append(audio_chunk)

                # 计算待处理音频的总时长
                pending_duration = audio_buffer.get_duration()

                # 检查是否有足够的音频需要处理
                if pending_duration >= min_audio_duration:
                    logger.info(f"Processing accumulated audio: {pending_duration:.2f}s")

                    # 获取满足最小时长的音频窗口
                    window_audio = audio_buffer.get_latest(pending_duration)

                    if len(window_audio) > 0:
                        logger.debug(f"Window audio size: {len(window_audio)} samples")
                        
                        # 如果有 VAD，使用 VAD 检测
                        if vad is not None:
                            try:
                                speech_timestamps = vad.detect_speech(
                                    window_audio, sample_rate
                                )
                                logger.debug(f"VAD detected {len(speech_timestamps)} speech segments")

                                if speech_timestamps:
                                    # 提取语音段落
                                    speech_audio = vad.extract_speech(
                                        window_audio, speech_timestamps, sample_rate=sample_rate
                                    )
                                else:
                                    logger.debug("No speech detected by VAD, skipping transcription")
                                    # 清空待处理缓冲区，继续等待新的音频
                                    audio_buffer.clear()
                                    continue
                            except Exception as e:
                                logger.warning(f"VAD detection failed: {e}, processing all audio")
                                speech_audio = window_audio
                        else:
                            # 没有 VAD，处理所有音频
                            speech_audio = window_audio

                        # 转录
                        try:
                            transcription_attempts += 1
                            logger.info(f"Transcription attempt #{transcription_attempts}")
                            
                            language = self.current_options.get('language')
                            text = await self.speech_engine.transcribe_stream(
                                speech_audio,
                                language=language
                            )

                            logger.info(f"Transcription result: '{text}'")

                            if text.strip():
                                # 去重检查：如果与上一次转录完全相同或高度相似，跳过
                                if self._is_duplicate_transcription(text, last_transcription):
                                    logger.debug(f"Duplicate transcription detected, skipping: {text[:50]}...")
                                else:
                                    # 累积转录文本
                                    self.accumulated_transcription.append(text)

                                    # 通知 UI 更新
                                    if self.on_transcription_update:
                                        try:
                                            self.on_transcription_update(text)
                                            logger.debug("UI callback invoked successfully")
                                        except Exception as e:
                                            logger.error(f"Error in transcription callback: {e}")

                                    # 将转录文本放入翻译队列
                                    enable_trans = self.current_options.get(
                                        'enable_translation', False
                                    )
                                    if enable_trans:
                                        await self.translation_queue.put(text)

                                    logger.info(f"Transcribed successfully: {text[:50]}...")
                                    
                                    # 更新上一次转录结果
                                    last_transcription = text
                            else:
                                logger.debug("Transcription returned empty text")
                        except Exception as e:
                            logger.error(f"Transcription failed: {e}", exc_info=True)
                            if self.on_error:
                                self.on_error(f"Transcription error: {e}")

                    # 清空待处理缓冲区（已处理完成）
                    audio_buffer.clear()

            except asyncio.TimeoutError:
                # 超时，继续等待
                continue
            except Exception as e:
                logger.error(f"Error in audio stream processing: {e}", exc_info=True)
                if self.on_error:
                    self.on_error(f"Processing error: {e}")
                if self.is_recording:
                    continue
                else:
                    break

        logger.info(f"Audio stream processing stopped. Total chunks: {audio_chunks_received}, Transcription attempts: {transcription_attempts}")

    async def _process_translation_stream(self):
        """处理翻译流的异步任务"""
        logger.info("Translation stream processing started")
        
        # 检查翻译引擎是否可用
        if not self.translation_engine:
            logger.warning("Translation engine not available")
            if self.on_error:
                self.on_error("Translation not available: No API key configured")
            return

        while self.is_recording or not self.translation_queue.empty():
            try:
                # 从队列获取转录文本（超时 0.5 秒）
                text = await asyncio.wait_for(
                    self.translation_queue.get(),
                    timeout=0.5
                )

                # 翻译
                source_lang = self.current_options.get('language', 'auto')
                target_lang = self.current_options.get('target_language', 'en')

                # 翻译引擎已在函数开始时检查
                translated_text = await self.translation_engine.translate(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang
                )

                if translated_text.strip():
                    # 累积翻译文本
                    self.accumulated_translation.append(translated_text)

                    # 通知 UI 更新
                    if self.on_translation_update:
                        self.on_translation_update(translated_text)

                    logger.debug(f"Translated: {translated_text}")

            except asyncio.TimeoutError:
                # 超时，继续等待
                continue
            except Exception as e:
                logger.error(f"Error in translation stream processing: {e}")
                if self.on_error:
                    self.on_error(f"Translation error: {e}")
                if self.is_recording:
                    continue
                else:
                    break

        logger.info("Translation stream processing stopped")

    async def stop_recording(self) -> Dict:
        """
        停止录制

        Returns:
            Dict: 录制结果
                {
                    'recording_path': str,  # 录音文件路径
                    'transcript_path': str,  # 转录文本路径
                    'duration': float,  # 录制时长（秒）
                    'event_id': str  # 日历事件 ID（如果创建）
                }
        """
        if not self.is_recording:
            logger.warning("Recording is not in progress")
            return {}

        logger.info("Stopping recording...")

        # 停止录制
        self.is_recording = False

        # 停止音频捕获
        if self.audio_capture is not None:
            self.audio_capture.stop_capture()

        # 等待处理任务完成
        if self.processing_task:
            try:
                await asyncio.wait_for(self.processing_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Processing task timeout")

        if self.translation_task:
            try:
                await asyncio.wait_for(self.translation_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Translation task timeout")

        # 计算录制时长
        recording_end_time = datetime.now()
        duration = (
            recording_end_time - self.recording_start_time
        ).total_seconds()

        if self.audio_buffer is not None:
            self.audio_buffer.clear()
            self.audio_buffer = None

        result = {
            'duration': duration,
            'start_time': self.recording_start_time.isoformat(),
            'end_time': recording_end_time.isoformat()
        }

        # 保存录音文件
        if self.current_options.get('save_recording', True):
            recording_path = await self._save_recording()
            result['recording_path'] = recording_path

        # 保存转录文本
        if self.current_options.get('save_transcript', True):
            transcript_path = await self._save_transcript()
            result['transcript_path'] = transcript_path

        # 保存翻译文本（如果启用了翻译）
        if self.current_options.get('enable_translation', False):
            translation_path = await self._save_translation()
            if translation_path:
                result['translation_path'] = translation_path

        # 创建日历事件
        if self.current_options.get('create_calendar_event', True):
            event_id = await self._create_calendar_event(result)
            result['event_id'] = event_id

        logger.info(f"Recording stopped: duration={duration:.2f}s")
        return result

    async def _save_recording(self) -> str:
        """
        保存录音文件

        Returns:
            str: 录音文件路径
        """
        if not self.recording_audio_buffer:
            logger.warning("No audio data to save")
            return ""

        # 合并所有音频块
        audio_data = np.concatenate(self.recording_audio_buffer)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        recording_format = self.current_options.get('recording_format', 'wav')
        filename = f"recording_{timestamp}.{recording_format}"

        # 保存文件
        try:
            # 创建临时文件
            temp_path = self.file_manager.get_temp_path(filename)

            # 写入音频数据
            write_rate = self.sample_rate if self.sample_rate and self.sample_rate > 0 else 16000
            sf.write(temp_path, audio_data, write_rate)

            # 移动到最终位置
            with open(temp_path, 'rb') as f:
                final_path = self.file_manager.save_file(
                    f.read(),
                    filename,
                    subdirectory='Recordings'
                )

            # 删除临时文件
            os.unlink(temp_path)

            logger.info(f"Recording saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            if self.on_error:
                self.on_error(f"Failed to save recording: {e}")
            return ""

    async def _save_transcript(self) -> str:
        """
        保存转录文本

        Returns:
            str: 转录文本文件路径
        """
        if not self.accumulated_transcription:
            logger.warning("No transcription data to save")
            return ""

        # 合并所有转录文本
        full_transcript = "\n".join(self.accumulated_transcription)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"transcript_{timestamp}.txt"

        # 保存文件
        try:
            final_path = self.file_manager.save_text_file(
                full_transcript,
                filename,
                subdirectory='Transcripts'
            )

            logger.info(f"Transcript saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            if self.on_error:
                self.on_error(f"Failed to save transcript: {e}")
            return ""

    async def _save_translation(self) -> str:
        """
        保存翻译文本

        Returns:
            str: 翻译文本文件路径
        """
        if not self.accumulated_translation:
            logger.warning("No translation data to save")
            return ""

        # 合并所有翻译文本
        full_translation = "\n".join(self.accumulated_translation)

        # 生成文件名
        timestamp = self.recording_start_time.strftime("%Y%m%d_%H%M%S")
        target_lang = self.current_options.get('target_language', 'en')
        filename = f"translation_{target_lang}_{timestamp}.txt"

        # 保存文件
        try:
            final_path = self.file_manager.save_text_file(
                full_translation,
                filename,
                subdirectory='Translations'
            )

            logger.info(f"Translation saved: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Failed to save translation: {e}")
            if self.on_error:
                self.on_error(f"Failed to save translation: {e}")
            return ""

    async def _create_calendar_event(self, recording_result: Dict) -> str:
        """
        创建日历事件

        Args:
            recording_result: 录制结果

        Returns:
            str: 事件 ID
        """
        try:
            from data.database.models import CalendarEvent, EventAttachment

            # 创建事件
            title_time = self.recording_start_time.strftime('%Y-%m-%d %H:%M')
            event = CalendarEvent(
                title=f"录音会话 - {title_time}",
                event_type='Event',
                start_time=recording_result['start_time'],
                end_time=recording_result['end_time'],
                description=f"录制时长: {recording_result['duration']:.2f} 秒",
                source='local'
            )
            event.save(self.db)

            # 添加附件
            if 'recording_path' in recording_result:
                rec_path = recording_result['recording_path']
                if rec_path and os.path.exists(rec_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='recording',
                        file_path=rec_path,
                        file_size=os.path.getsize(rec_path)
                    )
                    attachment.save(self.db)

            if 'transcript_path' in recording_result:
                trans_path = recording_result['transcript_path']
                if trans_path and os.path.exists(trans_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='transcript',
                        file_path=trans_path,
                        file_size=os.path.getsize(trans_path)
                    )
                    attachment.save(self.db)

            # 添加翻译附件（如果有）
            if 'translation_path' in recording_result:
                translation_path = recording_result['translation_path']
                if translation_path and os.path.exists(translation_path):
                    attachment = EventAttachment(
                        event_id=event.id,
                        attachment_type='translation',
                        file_path=translation_path,
                        file_size=os.path.getsize(translation_path)
                    )
                    attachment.save(self.db)

            logger.info(f"Calendar event created: {event.id}")
            return event.id

        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            if self.on_error:
                self.on_error(f"Failed to create calendar event: {e}")
            return ""

    async def get_transcription_stream(self) -> AsyncIterator[str]:
        """
        获取实时转录文本流

        Yields:
            str: 转录文本片段

        Note:
            在实际使用中，建议使用回调函数（set_callbacks）
            而不是这个生成器方法，因为回调函数更适合与 Qt Signal 集成
        """
        # 这个方法需要在实际使用中通过 Qt Signal 或其他机制实现
        # 这里提供一个基本框架
        while self.is_recording:
            # 等待转录结果
            await asyncio.sleep(0.1)
            # 实际实现应该从队列或缓冲区读取
            yield ""

    async def get_translation_stream(self) -> AsyncIterator[str]:
        """
        获取实时翻译文本流

        Yields:
            str: 翻译文本片段

        Note:
            在实际使用中，建议使用回调函数（set_callbacks）
            而不是这个生成器方法，因为回调函数更适合与 Qt Signal 集成
        """
        # 这个方法需要在实际使用中通过 Qt Signal 或其他机制实现
        # 这里提供一个基本框架
        while self.is_recording:
            # 等待翻译结果
            await asyncio.sleep(0.1)
            # 实际实现应该从队列或缓冲区读取
            yield ""

    def get_recording_duration(self) -> float:
        """
        获取当前录制时长

        Returns:
            float: 录制时长（秒）
        """
        if not self.is_recording or not self.recording_start_time:
            return 0.0

        return (datetime.now() - self.recording_start_time).total_seconds()

    def get_recording_status(self) -> Dict:
        """
        获取录制状态

        Returns:
            Dict: 录制状态信息
        """
        start_time = None
        if self.recording_start_time:
            start_time = self.recording_start_time.isoformat()

        return {
            'is_recording': self.is_recording,
            'duration': self.get_recording_duration(),
            'start_time': start_time,
            'buffer_size': len(self.recording_audio_buffer),
            'transcription_queue_size': self.transcription_queue.qsize(),
            'translation_queue_size': self.translation_queue.qsize(),
            'transcription_count': len(self.accumulated_transcription),
            'translation_count': len(self.accumulated_translation)
        }

    def get_accumulated_transcription(self) -> str:
        """
        获取累积的转录文本

        Returns:
            str: 完整的转录文本
        """
        return "\n".join(self.accumulated_transcription)

    def get_accumulated_translation(self) -> str:
        """
        获取累积的翻译文本

        Returns:
            str: 完整的翻译文本
        """
        return "\n".join(self.accumulated_translation)
    
    def _is_duplicate_transcription(self, new_text: str, last_text: str) -> bool:
        """
        检查新转录文本是否与上一次重复

        Args:
            new_text: 新的转录文本
            last_text: 上一次的转录文本

        Returns:
            bool: 是否重复
        """
        if not last_text:
            return False
        
        # 完全相同
        if new_text == last_text:
            return True
        
        # 计算相似度（使用简单的字符串包含检查）
        # 如果新文本完全包含在旧文本中，或旧文本完全包含在新文本中
        new_lower = new_text.lower().strip()
        last_lower = last_text.lower().strip()
        
        # 如果一个文本是另一个的子串，且长度差异不大，认为是重复
        if new_lower in last_lower or last_lower in new_lower:
            length_ratio = min(len(new_lower), len(last_lower)) / max(len(new_lower), len(last_lower))
            if length_ratio > 0.7:  # 70% 相似度阈值
                return True
        
        return False
