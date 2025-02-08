import pytest
from pathlib import Path
from asset_scanner.parser.class_parser import ClassParser
from asset_scanner.scanner_parallel import ParallelScanner
from asset_scanner.scanner_tasks import TaskPriority, TaskStatus, ScanTask
from asset_scanner.pbo_extractor import PboExtractor
from tests.conftest import BABE_EM_PBO_FILE, EM_BABE_EXPECTED, HEADBAND_EXPECTED, HEADBAND_PBO_FILE, MIRROR_EXPECTED, MIRRORFORM_PBO_FILE, PBO_FILES


@pytest.fixture
def sample_pbos() -> dict:
    """Collection of sample PBO files"""
    return {
        'mirror': (MIRRORFORM_PBO_FILE, MIRROR_EXPECTED),
        'headband': (HEADBAND_PBO_FILE, HEADBAND_EXPECTED),
        'em_babe': (BABE_EM_PBO_FILE, EM_BABE_EXPECTED)
    }


@pytest.fixture
def parallel_scanner(tmp_path: Path) -> ParallelScanner:
    extractor = PboExtractor()
    parser = ClassParser()
    return ParallelScanner(extractor, parser, max_workers=2)


def test_error_handling(parallel_scanner: ParallelScanner, tmp_path: Path) -> None:
    """Test error handling with invalid PBO"""
    invalid_pbo = tmp_path / "invalid.pbo"
    invalid_pbo.write_bytes(b"This is not a valid PBO file")

    task = ScanTask(
        path=invalid_pbo,
        priority=TaskPriority.HIGH,
        task_type='pbo',
        source='test'
    )

    result = parallel_scanner._process_task(task)
    assert result is None, "Should return None for invalid PBO"
    assert task.status == TaskStatus.FAILED, "Task should be marked as failed"


def test_empty_directory(parallel_scanner: ParallelScanner, tmp_path: Path) -> None:
    """Test scanning an empty directory"""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    results = parallel_scanner.scan_directories([empty_dir], "test")
    assert len(results) == 0

    # Verify task stats
    stats = parallel_scanner.task_manager.get_stats()
    assert stats[TaskStatus.COMPLETED] == 0
    assert stats[TaskStatus.FAILED] == 0
    assert stats[TaskStatus.PENDING] == 0


def test_invalid_directory(parallel_scanner: ParallelScanner) -> None:
    """Test scanning a non-existent directory"""
    results = parallel_scanner.scan_directories([Path("/nonexistent")], "test")
    assert len(results) == 0

    stats = parallel_scanner.task_manager.get_stats()
    assert stats[TaskStatus.FAILED] == 0  # Should not create tasks for invalid directory


def test_task_priority(parallel_scanner: ParallelScanner, tmp_path: Path) -> None:
    """Test task priority handling"""
    mod_dir = tmp_path / "@test_mod"
    mod_dir.mkdir()
    addons_dir = mod_dir / "addons"
    addons_dir.mkdir()

    # Create dummy files with different priorities
    high_prio = addons_dir / "config.pbo"
    high_prio.write_bytes(b"dummy")
    med_prio = addons_dir / "content.pbo"
    med_prio.write_bytes(b"dummy")
    low_prio = addons_dir / "optional.pbo"
    low_prio.write_bytes(b"dummy")

    # Add tasks with different priorities
    parallel_scanner.task_manager.add_task(ScanTask(
        path=high_prio,
        priority=TaskPriority.HIGH,
        task_type='pbo',
        source='test'
    ))
    parallel_scanner.task_manager.add_task(ScanTask(
        path=med_prio,
        priority=TaskPriority.MEDIUM,
        task_type='pbo',
        source='test'
    ))
    parallel_scanner.task_manager.add_task(ScanTask(
        path=low_prio,
        priority=TaskPriority.LOW,
        task_type='pbo',
        source='test'
    ))

    # Get next tasks and verify order
    tasks = parallel_scanner.task_manager.get_next_tasks(limit=3)
    assert len(tasks) == 3
    assert tasks[0].priority == TaskPriority.HIGH
    assert tasks[1].priority == TaskPriority.MEDIUM
    assert tasks[2].priority == TaskPriority.LOW


def test_task_dependencies(parallel_scanner: ParallelScanner, tmp_path: Path) -> None:
    """Test handling of task dependencies"""
    mod_dir = tmp_path / "@test_mod"
    mod_dir.mkdir()
    addons_dir = mod_dir / "addons"
    addons_dir.mkdir()

    # Create dummy files with dependencies
    main_pbo = addons_dir / "main.pbo"
    main_pbo.write_bytes(b"dummy")
    dep_pbo = addons_dir / "dependency.pbo"
    dep_pbo.write_bytes(b"dummy")

    # Create tasks with dependency
    dep_task = ScanTask(
        path=dep_pbo,
        priority=TaskPriority.HIGH,
        task_type='pbo',
        source='test'
    )
    main_task = ScanTask(
        path=main_pbo,
        priority=TaskPriority.HIGH,
        task_type='pbo',
        source='test',
        dependencies={dep_pbo}
    )

    parallel_scanner.task_manager.add_task(main_task)
    parallel_scanner.task_manager.add_task(dep_task)

    # First batch should only include dependency
    tasks = parallel_scanner.task_manager.get_next_tasks(limit=1)
    assert len(tasks) == 1
    assert tasks[0].path == dep_pbo

    # Complete dependency
    parallel_scanner.task_manager.complete_task(dep_pbo)

    # Now main task should be available
    tasks = parallel_scanner.task_manager.get_next_tasks(limit=1)
    assert len(tasks) == 1
    assert tasks[0].path == main_pbo


def test_asset_detection(parallel_scanner: ParallelScanner, sample_pbos: dict) -> None:
    """Test that assets are correctly found in PBO files"""
    for name, (pbo_path, expected_paths) in sample_pbos.items():
        task = ScanTask(
            path=pbo_path,
            priority=TaskPriority.HIGH,
            task_type='pbo',
            source=name
        )

        # Use the inherited _scan_pbo method from BaseScanner
        result = parallel_scanner._scan_pbo(task)
        assert result is not None, f"Processing {name} PBO should return a result"

        # Process found paths to match expected format
        found_paths = set()
        for asset in result.assets:
            # Get the normalized path and remove any source/addons prefix
            path_str = str(asset.path).replace('\\', '/').strip('/')
            
            # Ensure the path doesn't start with the source or addons
            parts = path_str.split('/')
            while parts and parts[0] in {'addons', asset.source, 'tc'}:
                parts.pop(0)
            
            if parts:
                found_paths.add('/'.join(parts))

        # Filter out binary and source files from comparison
        found_paths = {p for p in found_paths if not p.endswith(('.bin', '.cpp', '.hpp'))}
        
        # Compare with expected paths
        extra = found_paths - expected_paths
        missing = expected_paths - found_paths

        assert not extra, f"Found unexpected files in {name}: {sorted(extra)}"
        assert not missing, f"Missing expected files in {name}: {sorted(missing)}"
