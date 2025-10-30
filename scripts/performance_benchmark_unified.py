#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Unified performance benchmark for PySide6 migration.
Measures all performance aspects in a single, focused script.
"""

import argparse
import json
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.benchmark_config import BenchmarkConfig
from utils.logger import setup_logging

class UnifiedBenchmark:
    """Unified performance benchmark."""

    def __init__(self, output_dir: str = "benchmark_results"):
        """Initialize benchmark."""
        self.logger = logging.getLogger(__name__)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.process = psutil.Process(os.getpid())
        self.config = BenchmarkConfig()

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": self.config.get_system_info(),
            "baselines": self.config.BASELINES,
        }

    def measure_startup_time(self) -> Dict:
        """Measure application startup time."""
        self.logger.info("Measuring startup time...")

        cold_times = []
        hot_times = []

        for i in range(self.config.TEST_PARAMS["startup_runs"]):
            self.logger.info(f"Startup test run {i + 1}")

            # Cold start
            self._clear_caches()
            cold_time = self._measure_single_startup()
            if cold_time < float("inf"):
                cold_times.append(cold_time)

            # Hot start
            hot_time = self._measure_single_startup()
            if hot_time < float("inf"):
                hot_times.append(hot_time)

            time.sleep(1)

        if not cold_times or not hot_times:
            return {"error": "Startup measurement failed"}

        return {
            "cold_avg": statistics.mean(cold_times),
            "hot_avg": statistics.mean(hot_times),
            "cold_times": cold_times,
            "hot_times": hot_times,
        }

    def _clear_caches(self):
        """Clear system caches for cold start."""
        try:
            if self.config.get_system_info()["system"] == "Darwin":  # macOS
                subprocess.run(["sudo", "purge"], check=False, capture_output=True)
        except Exception:
            pass  # Cache clearing is optional

    def _measure_single_startup(self) -> float:
        """Measure single startup time."""
        test_script = f"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

start_time = time.time()

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)

    from config.app_config import ConfigManager
    from utils.i18n import I18nQtManager

    config = ConfigManager()
    i18n = I18nQtManager()

    startup_time = time.time() - start_time
    print(f"STARTUP_TIME:{{startup_time:.3f}}")

    QTimer.singleShot(100, app.quit)
    app.exec()

except Exception as e:
    print(f"ERROR:{{e}}")
    sys.exit(1)
"""

        test_script_path = self.output_dir / "startup_test.py"
        try:
            with open(test_script_path, "w") as f:
                f.write(test_script)

            result = subprocess.run(
                [sys.executable, str(test_script_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=Path(__file__).parent.parent,
            )

            for line in result.stdout.split("\n"):
                if line.startswith("STARTUP_TIME:"):
                    return float(line.split(":")[1])

            return float("inf")

        except Exception:
            return float("inf")
        finally:
            if test_script_path.exists():
                test_script_path.unlink()

    def measure_ui_response(self) -> Dict:
        """Measure UI response times."""
        self.logger.info("Measuring UI response times...")

        try:

                QApplication,
                QDialog,
                QLabel,
                QListWidget,
                QListWidgetItem,
                QMainWindow,
                QMenuBar,
                QPushButton,
                QVBoxLayout,
            )

            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)

            results = {}

            # Button response
            window = QMainWindow()
            button = QPushButton("Test")
            window.setCentralWidget(button)
            window.show()
            app.processEvents()

            button_times = []
            for _ in range(self.config.TEST_PARAMS["ui_button_iterations"]):
                start = time.perf_counter()
                button.click()
                app.processEvents()
                button_times.append(time.perf_counter() - start)

            results["button_response"] = statistics.mean(button_times)
            window.close()

            # Menu response
            window = QMainWindow()
            menubar = window.menuBar()
            menu = menubar.addMenu("Test")
            menu.addAction("Action")
            window.show()
            app.processEvents()

            menu_times = []
            for _ in range(self.config.TEST_PARAMS["ui_menu_iterations"]):
                start = time.perf_counter()
                menu.exec(window.mapToGlobal(window.rect().topLeft()))
                app.processEvents()
                menu_times.append(time.perf_counter() - start)

            results["menu_response"] = statistics.mean(menu_times)
            window.close()

            # Dialog response
            parent = QMainWindow()
            parent.show()
            app.processEvents()

            dialog_times = []
            for _ in range(self.config.TEST_PARAMS["ui_dialog_iterations"]):
                start = time.perf_counter()
                dialog = QDialog(parent)
                dialog.setLayout(QVBoxLayout())
                dialog.show()
                app.processEvents()
                dialog_times.append(time.perf_counter() - start)
                dialog.close()

            results["dialog_response"] = statistics.mean(dialog_times)
            parent.close()

            return results

        except Exception as e:
            return {"error": str(e)}

    def measure_memory_usage(self) -> Dict:
        """Measure memory usage."""
        self.logger.info("Measuring memory usage...")

        try:
            # Baseline memory
            import gc

            gc.collect()
            baseline = self.process.memory_info().rss / 1024 / 1024

            # After PySide6 import
            from PySide6.QtWidgets import QApplication

            after_qt = self.process.memory_info().rss / 1024 / 1024

            # After UI creation
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)

            from config.app_config import ConfigManager
            from utils.i18n import I18nQtManager

            config = ConfigManager()
            i18n = I18nQtManager()

            after_core = self.process.memory_info().rss / 1024 / 1024

            # Memory over time (simplified)
            initial_memory = after_core
            time.sleep(5)  # Brief monitoring
            final_memory = self.process.memory_info().rss / 1024 / 1024

            return {
                "baseline": baseline,
                "after_qt": after_qt,
                "after_core": after_core,
                "qt_overhead": after_qt - baseline,
                "core_overhead": after_core - after_qt,
                "memory_growth": final_memory - initial_memory,
                "final_memory": final_memory,
            }

        except Exception as e:
            return {"error": str(e)}

    def measure_functional_performance(self) -> Dict:
        """Measure functional performance."""
        self.logger.info("Measuring functional performance...")

        results = {}

        # Database performance
        try:
            results["database"] = self._test_database_performance()
        except Exception as e:
            results["database"] = {"error": str(e)}

        # File operations
        try:
            results["file_operations"] = self._test_file_performance()
        except Exception as e:
            results["file_operations"] = {"error": str(e)}

        # Calendar operations (simplified)
        try:
            results["calendar"] = self._test_calendar_performance()
        except Exception as e:
            results["calendar"] = {"error": str(e)}

        return results

    def _test_database_performance(self) -> Dict:
        """Test database performance."""
        from data.database.connection import DatabaseConnection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            db = DatabaseConnection(temp_db_path)
            db.initialize_schema()

            # Insert test
            records = self.config.TEST_PARAMS["database_test_records"]
            start = time.time()

            for i in range(records):
                db.execute(
                    "INSERT INTO transcription_tasks (file_path, status, created_at) VALUES (?, ?, ?)",
                    (f"/test/file_{i}.wav", "pending", datetime.now()),
                )

            insert_time = time.time() - start
            insert_rate = records / insert_time if insert_time > 0 else 0

            # Select test
            start = time.time()
            results = db.execute("SELECT * FROM transcription_tasks WHERE status = ?", ("pending",))
            select_time = time.time() - start
            select_rate = len(results) / select_time if select_time > 0 else 0

            return {
                "insert_rate": insert_rate,
                "select_rate": select_rate,
                "records_tested": records,
            }

        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def _test_file_performance(self) -> Dict:
        """Test file performance."""
        from data.storage.file_manager import FileManager

        with tempfile.TemporaryDirectory() as temp_dir:
            file_manager = FileManager(temp_dir)

            files = self.config.TEST_PARAMS["file_test_count"]
            test_content = "Test content for performance measurement"

            # Create files
            start = time.time()
            created_files = []

            for i in range(files):
                filename = f"test_{i:06d}.txt"
                file_path = file_manager.save_transcript(filename, test_content)
                created_files.append(file_path)

            create_time = time.time() - start
            create_rate = files / create_time if create_time > 0 else 0

            # Read files
            start = time.time()
            read_count = 0

            for file_path in created_files:
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        if f.read():
                            read_count += 1

            read_time = time.time() - start
            read_rate = read_count / read_time if read_time > 0 else 0

            return {
                "create_rate": create_rate,
                "read_rate": read_rate,
                "files_tested": files,
            }

    def _test_calendar_performance(self) -> Dict:
        """Test calendar performance."""
        from core.calendar.manager import CalendarManager
        from data.database.connection import DatabaseConnection

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name

        try:
            db = DatabaseConnection(temp_db_path)
            db.initialize_schema()

            calendar_manager = CalendarManager(db, {})

            events = self.config.TEST_PARAMS["calendar_test_events"]
            base_time = datetime.now()

            # Create events
            start = time.time()

            for i in range(events):
                calendar_manager.create_event(
                    title=f"Test Event {i}",
                    description=f"Description {i}",
                    start_time=base_time,
                    end_time=base_time,
                    calendar_id="test",
                )

            create_time = time.time() - start
            create_rate = events / create_time if create_time > 0 else 0

            return {
                "create_rate": create_rate,
                "events_tested": events,
            }

        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks."""
        self.logger.info("Starting unified performance benchmark...")

        # Run benchmarks
        self.results["startup"] = self.measure_startup_time()
        self.results["ui_response"] = self.measure_ui_response()
        self.results["memory"] = self.measure_memory_usage()
        self.results["functional"] = self.measure_functional_performance()

        # Compare with baselines
        self.results["comparison"] = self._compare_with_baselines()

        return self.results

    def _compare_with_baselines(self) -> Dict:
        """Compare results with baselines."""
        comparison = {}

        # Startup comparison
        if "startup" in self.results and "cold_avg" in self.results["startup"]:
            cold_avg = self.results["startup"]["cold_avg"]
            comparison["startup_cold"] = {
                "measured": cold_avg,
                "baseline": self.config.BASELINES["startup_time_cold"],
                "pass": cold_avg <= self.config.BASELINES["startup_time_cold"],
            }

        if "startup" in self.results and "hot_avg" in self.results["startup"]:
            hot_avg = self.results["startup"]["hot_avg"]
            comparison["startup_hot"] = {
                "measured": hot_avg,
                "baseline": self.config.BASELINES["startup_time_hot"],
                "pass": hot_avg <= self.config.BASELINES["startup_time_hot"],
            }

        # UI response comparison
        if "ui_response" in self.results:
            ui = self.results["ui_response"]
            if "button_response" in ui:
                comparison["ui_button"] = {
                    "measured": ui["button_response"],
                    "baseline": self.config.BASELINES["ui_response_button"],
                    "pass": ui["button_response"] <= self.config.BASELINES["ui_response_button"],
                }

        # Memory comparison
        if "memory" in self.results:
            memory = self.results["memory"]
            if "final_memory" in memory:
                comparison["memory_usage"] = {
                    "measured": memory["final_memory"],
                    "baseline": self.config.BASELINES["memory_idle"],
                    "pass": memory["final_memory"] <= self.config.BASELINES["memory_idle"] * 1.1,
                }

        return comparison

    def save_results(self):
        """Save benchmark results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_results_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)

        # Save as latest
        latest_path = self.output_dir / "benchmark_results_latest.json"
        with open(latest_path, "w") as f:
            json.dump(self.results, f, indent=2)

        self.logger.info(f"Results saved to: {filepath}")

    def print_summary(self):
        """Print benchmark summary."""
        print("\n" + "=" * 60)
        print("PYSIDE6 PERFORMANCE BENCHMARK SUMMARY")
        print("=" * 60)

        # System info
        sys_info = self.results["system_info"]
        print(f"System: {sys_info['platform']}")
        print(f"Python: {sys_info['python_version']}")
        print(f"Memory: {sys_info['memory_total']:.1f} MB")
        print()

        # Results
        if "startup" in self.results and "cold_avg" in self.results["startup"]:
            startup = self.results["startup"]
            print(f"Startup (cold): {startup['cold_avg']:.2f}s")
            print(f"Startup (hot): {startup['hot_avg']:.2f}s")

        if "ui_response" in self.results and "button_response" in self.results["ui_response"]:
            ui = self.results["ui_response"]
            print(f"Button response: {ui['button_response']*1000:.1f}ms")

        if "memory" in self.results and "final_memory" in self.results["memory"]:
            memory = self.results["memory"]
            print(f"Memory usage: {memory['final_memory']:.1f} MB")

        # Comparison
        if "comparison" in self.results:
            comparison = self.results["comparison"]
            passed = sum(1 for comp in comparison.values() if comp.get("pass", False))
            total = len(comparison)

            print(f"\nBaseline comparison: {passed}/{total} passed")

            for name, comp in comparison.items():
                status = "PASS" if comp.get("pass", False) else "FAIL"
                print(f"  {name}: {status}")

        print("=" * 60)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Unified performance benchmark")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    # Run benchmark
    benchmark = UnifiedBenchmark(args.output_dir)
    results = benchmark.run_all_benchmarks()
    benchmark.save_results()
    benchmark.print_summary()

    # Exit with error code if tests failed
    if "comparison" in results:
        failed = sum(1 for comp in results["comparison"].values() if not comp.get("pass", False))
        if failed > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()
