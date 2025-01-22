import pytest
import time
from pathlib import Path
from asset_scanner import AssetAPI, APIConfig

@pytest.fixture
def large_structure(tmp_path):
    """Create a large test structure"""
    for i in range(100):
        mod_dir = tmp_path / f"@mod_{i}"
        mod_dir.mkdir()
        for j in range(10):
            (mod_dir / f"file_{j}.p3d").write_text("test")
    return tmp_path

def test_batch_performance(large_structure):
    """Test performance of batch processing"""
    api = AssetAPI(Path("test"))
    
    start = time.time()
    api.scan_directory(large_structure)
    scan_time = time.time() - start
    
    # Test different batch sizes
    batch_sizes = [10, 100, 1000]
    times = {}
    
    for size in batch_sizes:
        start = time.time()
        processed = []
        api.batch_process(processed.append, batch_size=size)
        times[size] = time.time() - start
    
    # Verify larger batches are generally faster
    assert times[1000] <= times[10]

def test_concurrent_scanning(large_structure):
    """Test concurrent scanning performance"""
    config = APIConfig(max_workers=4)
    api = AssetAPI(Path("test"), config=config)
    
    paths = [p for p in large_structure.iterdir()]
    
    start = time.time()
    results = api.scan_multiple(paths)
    parallel_time = time.time() - start
    
    # Should complete in reasonable time
    assert parallel_time < 30  # Adjust based on actual performance needs
