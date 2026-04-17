import fcntl
import json
from pathlib import Path
from typing import Any, Dict, Callable
from contextlib import contextmanager
import threading


class FileLock:
    """Thread-safe file lock for atomic operations"""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._fd = None
    
    def __enter__(self):
        self._lock.acquire()
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.filepath, 'a')
        fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fd:
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            self._fd.close()
        self._lock.release()
    
    @contextmanager
    def read_json(self) -> Dict[str, Any]:
        """Read JSON file with lock and handle empty files"""
        with self:
            if not self.filepath.exists():
                yield {}
                return
            
            try:
                with open(self.filepath, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        # Empty file
                        yield {}
                        return
                    
                    data = json.loads(content)
                    yield data
            except json.JSONDecodeError as e:
                # Log error and return empty dict
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"JSON decode error in {self.filepath}: {e}")
                
                # Backup corrupted file
                backup = self.filepath.with_suffix('.json.corrupted')
                import shutil
                shutil.copy2(self.filepath, backup)
                logger.info(f"Backed up corrupted file to {backup}")
                
                yield {}
    
    @contextmanager
    def write_json(self, data: Dict[str, Any]) -> None:
        """Write JSON file with lock"""
        with self:
            # Write to temp file first for atomicity
            temp_path = self.filepath.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.filepath)
            yield


class AtomicFileWriter:
    """Atomic file writer with backup"""
    
    def __init__(self, filepath: Path, backup: bool = True):
        self.filepath = filepath
        self.backup = backup
        self.temp_path = filepath.with_suffix('.tmp')
        self.backup_path = filepath.with_suffix('.bak')
    
    def __enter__(self):
        return self.temp_path.open('w')
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Create backup if requested
            if self.backup and self.filepath.exists():
                import shutil
                shutil.copy2(self.filepath, self.backup_path)
            
            # Replace with new file
            self.temp_path.replace(self.filepath)
        else:
            # Clean up temp file on error
            self.temp_path.unlink(missing_ok=True)

