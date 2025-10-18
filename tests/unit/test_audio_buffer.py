import threading

import pytest

np = pytest.importorskip("numpy")

from core.realtime.audio_buffer import AudioBuffer


def test_append_and_get_all_preserves_order():
    buffer = AudioBuffer(max_duration_seconds=5, sample_rate=4)

    first_chunk = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
    second_chunk = np.array([0.5, 0.6, 0.7, 0.8], dtype=np.float32)

    buffer.append(first_chunk)
    buffer.append(second_chunk)

    all_data = buffer.get_all()

    expected = np.concatenate([first_chunk, second_chunk])
    np.testing.assert_array_equal(all_data, expected)
    assert buffer.get_size() == len(expected)


def test_get_window_with_offset_returns_expected_segment():
    buffer = AudioBuffer(max_duration_seconds=5, sample_rate=4)
    full_sequence = np.arange(0, 20, dtype=np.float32)
    buffer.append(full_sequence)

    window = buffer.get_window(duration_seconds=2.0, offset_seconds=1.0)

    # 最新数据在末尾，偏移 1s 后应从第 8 个样本开始取 8 个样本
    expected = full_sequence[8:16]
    np.testing.assert_array_equal(window, expected)


def test_get_sliding_windows_respects_overlap():
    buffer = AudioBuffer(max_duration_seconds=5, sample_rate=4)
    buffer.append(np.arange(0, 16, dtype=np.float32))

    windows = buffer.get_sliding_windows(window_duration_seconds=1.0, overlap_seconds=0.5)

    assert len(windows) == 7  # 0,2,4,6,8,10,12 起始位置
    first_window = np.arange(0, 4, dtype=np.float32)
    middle_window = np.arange(6, 10, dtype=np.float32)

    np.testing.assert_array_equal(windows[0], first_window)
    np.testing.assert_array_equal(windows[3], middle_window)


def test_thread_safe_append_preserves_total_length():
    buffer = AudioBuffer(max_duration_seconds=50, sample_rate=100)
    thread_count = 4
    iterations = 5
    chunk_size = 100

    def worker(offset: float):
        chunk = np.full(chunk_size, offset, dtype=np.float32)
        for _ in range(iterations):
            buffer.append(chunk)

    threads = [threading.Thread(target=worker, args=(float(i),)) for i in range(thread_count)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    expected_samples = thread_count * iterations * chunk_size
    assert buffer.get_size() == expected_samples
    assert buffer.total_samples_added == expected_samples
