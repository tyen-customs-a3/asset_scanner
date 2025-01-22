# Asset Scanner

A high-performance asset scanner for game content with multi-threaded processing, smart caching, and comprehensive asset management capabilities.

## Features

- Multi-threaded scanning with automatic CPU core optimization
- Path normalization and case-insensitive lookups
- Smart caching with immutable data structures
- PBO archive analysis with prefix preservation
- Extension and pattern-based filtering
- Progress tracking support
- Source-based asset organization
- Related asset discovery
- Game folder structure support

## Requirements

- Python 3.8+
- extractpbo tool in system PATH
- Read permissions for target directories

## Usage

### Basic Scanning

```python
from asset_scanner import AssetAPI
from pathlib import Path

# Initialize API with cache directory
api = AssetAPI(Path("cache"))

# Scan a directory
result = api.scan_directory(Path("@mod"))

# Get all assets
assets = api.get_all_assets()

# Find assets by extension
textures = api.find_by_extension(".paa")

# Search with pattern
configs = api.find_by_pattern(r"config\.cpp$")
```

### Asset Management

```python
# Get asset by path
asset = api.get_asset("@mod/textures/example.paa")

# Find related assets
if asset:
    related = api.find_related(asset)

# Check for duplicates
duplicates = api.find_duplicates()

# Get source-specific assets
mod_assets = api.get_assets_by_source("@mod")
```

### Batch Operations

```python
# Verify multiple assets
paths = ["texture1.paa", "model1.p3d"]
results = api.verify_assets(paths)

# Find missing assets
missing = api.find_missing(paths)

# Process assets in batches
for batch in api.iter_assets(batch_size=1000):
    process_assets(batch)
```

### Path Handling

```python
# Normalize a path
normalized_path = api.normalize_path("@mod\\textures\\example.paa")

# Check if a path has a PBO prefix
has_prefix = api.has_pbo_prefix(normalized_path)
```

### Game Folder Structure

```python
# Scan game folder structure
game_assets = api.scan_game_folder_structure(Path("game_folder"))
```

### Asset Properties

Each Asset object contains:
- path: Normalized path
- source: Origin mod/source
- last_scan: Timestamp
- has_prefix: PBO prefix status
- pbo_path: Optional PBO container path

## Development

### Project Structure

- `api.py`: Main API interface
- `scanner.py`: Core scanning logic
- `cache.py`: Caching implementation
- `models.py`: Data models

### Key Classes

- `AssetAPI`: Main interface for all operations
- `AssetScanner`: Core scanning engine
- `AssetCache`: Immutable cache container
- `AssetCacheManager`: Thread-safe cache access

## License

MIT License