from abc import ABC, abstractmethod
from pathlib import Path
import aiofiles
import asyncio
import logging
import os
import shutil
from typing import List, Optional
from contextvars import ContextVar
import re

logger = logging.getLogger("pencms.storage")

# Global context for vault-provided secrets (e.g. SFTP passwords)
# This is populated per-request by the API auth dependency.
vault_secrets: ContextVar[dict] = ContextVar("vault_secrets", default={})

class BaseStorageProvider(ABC):
    @abstractmethod
    async def read(self, path: str) -> str:
        """Read a file as a string."""
        pass

    @abstractmethod
    async def read_bytes(self, path: str) -> bytes:
        """Read a file as bytes."""
        pass

    @abstractmethod
    async def write(self, path: str, content: str):
        """Write a string to a file."""
        pass

    @abstractmethod
    async def write_bytes(self, path: str, content: bytes):
        """Write bytes to a file."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a path exists."""
        pass

    @abstractmethod
    async def is_dir(self, path: str) -> bool:
        """Check if a path is a directory."""
        pass

    @abstractmethod
    async def delete(self, path: str):
        """Delete a file."""
        pass

    @abstractmethod
    async def delete_dir(self, path: str):
        """Delete a directory and its contents."""
        pass

    @abstractmethod
    async def list_dir(self, path: str, recursive: bool = False) -> List[str]:
        """List contents of a directory. Returns relative paths as strings."""
        pass

    @abstractmethod
    async def mkdir(self, path: str, parents: bool = True):
        """Create a directory."""
        pass

    @abstractmethod
    async def stat(self, path: str) -> dict:
        """Get file stats (size, modified time)."""
        pass

    async def begin_transaction(self):
        """Start a batch of operations. Default is a no-op."""
        pass

    async def end_transaction(self, message: str = "Automated update"):
        """Finalize a batch of operations. Default is a no-op."""
        pass

    async def cancel_transaction(self):
        """Abort a batch of operations and reset state. Default is a no-op."""
        pass

    async def close(self):
        """Clean up resources (connections, sockets). Default is a no-op."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()

    def _resolve(self, path: str) -> Path:
        """Resolve a relative path against the base path and prevent traversal."""
        clean_path = path.lstrip("/")
        resolved = (self.base_path / clean_path).resolve()
        
        # Ensure the resolved path is within the base_path
        if not str(resolved).startswith(str(self.base_path) + os.sep) and resolved != self.base_path:
            raise ValueError(f"Path traversal blocked: {path!r} escapes base directory")
            
        return resolved

    async def read(self, path: str) -> str:
        full_path = self._resolve(path)
        async with aiofiles.open(full_path, mode='r', encoding='utf-8') as f:
            return await f.read()

    async def read_bytes(self, path: str) -> bytes:
        full_path = self._resolve(path)
        async with aiofiles.open(full_path, mode='rb') as f:
            return await f.read()

    async def write(self, path: str, content: str):
        full_path = self._resolve(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full_path, mode='w', encoding='utf-8') as f:
            await f.write(content)

    async def write_bytes(self, path: str, content: bytes):
        full_path = self._resolve(path)
        # Ensure parent exists (blocking call, but safe enough for local FS; 
        # could be moved to thread if needed)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(full_path, mode='wb') as f:
            await f.write(content)

    async def exists(self, path: str) -> bool:
        full_path = self._resolve(path)
        return await asyncio.to_thread(full_path.exists)

    async def is_dir(self, path: str) -> bool:
        full_path = self._resolve(path)
        return await asyncio.to_thread(full_path.is_dir)

    async def delete(self, path: str):
        full_path = self._resolve(path)
        if await asyncio.to_thread(full_path.exists):
            await asyncio.to_thread(full_path.unlink)

    async def delete_dir(self, path: str):
        full_path = self._resolve(path)
        if await asyncio.to_thread(full_path.exists) and await asyncio.to_thread(full_path.is_dir):
            await asyncio.to_thread(shutil.rmtree, full_path)

    async def list_dir(self, path: str, recursive: bool = False) -> List[str]:
        full_path = self._resolve(path)
        if not await asyncio.to_thread(full_path.exists) or not await asyncio.to_thread(full_path.is_dir):
            return []
        
        results = []
        if recursive:
            # Wrap the entire rglob/iterdir loop in a thread for large trees
            def sync_rglob():
                return [str(p.relative_to(full_path)) for p in full_path.rglob("*") if p.is_file()]
            results = await asyncio.to_thread(sync_rglob)
        else:
            def sync_iterdir():
                return [str(p.relative_to(full_path)) for p in full_path.iterdir()]
            results = await asyncio.to_thread(sync_iterdir)
            
        return sorted(results)

    async def mkdir(self, path: str, parents: bool = True):
        full_path = self._resolve(path)
        await asyncio.to_thread(full_path.mkdir, parents=parents, exist_ok=True)

    async def stat(self, path: str) -> dict:
        full_path = self._resolve(path)
        s = await asyncio.to_thread(full_path.stat)
        return {
            "size": s.st_size,
            "mtime": s.st_mtime,
            "ctime": s.st_ctime
        }


class GitStorageProvider(LocalStorageProvider):
    def __init__(self, base_path: str):
        super().__init__(base_path)
        self.in_transaction = False
        self.has_changes = False
        self._initialized = False
        self._git_lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()

    async def _ensure_initialized(self):
        """Perform one-time git setup if needed."""
        async with self._init_lock:
            if self._initialized:
                return
            await self.initial_setup()
            self._initialized = True

    async def _run_git(self, *args) -> bool:
        """Run a git command in the base directory."""
        import subprocess
        async with self._git_lock:
            def sync_git():
                try:
                    cmd = ["git", *args]
                    result = subprocess.run(
                        cmd,
                        cwd=str(self.base_path),
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if result.returncode != 0:
                        print(f"Git error ({' '.join(args)}): {result.stderr}")
                    return result.returncode == 0
                except Exception as e:
                    print(f"Git execution failed: {e}")
                    return False
            
            return await asyncio.to_thread(sync_git)

    async def initial_setup(self):
        """Initialize git repo if missing."""
        if not (self.base_path / ".git").exists():
            await self._run_git("init")
            # Set local config to prevent "identity unknown" errors
            await self._run_git("config", "user.name", "pencms CMS")
            await self._run_git("config", "user.email", "cms@pencms.local")

    async def begin_transaction(self):
        await self._ensure_initialized()
        self.in_transaction = True
        self.has_changes = False

    async def end_transaction(self, message: str = "Automated update"):
        if self.has_changes:
            await self._ensure_initialized()
            await self._run_git("add", ".")
            await self._run_git("commit", "-m", message)
        self.in_transaction = False
        self.has_changes = False

    async def cancel_transaction(self):
        self.in_transaction = False
        self.has_changes = False

    async def write(self, path: str, content: str):
        await super().write(path, content)
        self.has_changes = True
        if not self.in_transaction:
            await self._ensure_initialized()
            await self.end_transaction(f"Updated {path}")

    async def write_bytes(self, path: str, content: bytes):
        await super().write_bytes(path, content)
        self.has_changes = True
        if not self.in_transaction:
            await self._ensure_initialized()
            await self.end_transaction(f"Updated {path} (binary)")

    async def delete(self, path: str):
        await super().delete(path)
        self.has_changes = True
        if not self.in_transaction:
            await self._ensure_initialized()
            await self.end_transaction(f"Deleted {path}")

    async def delete_dir(self, path: str):
        await super().delete_dir(path)
        self.has_changes = True
        if not self.in_transaction:
            await self._ensure_initialized()
            await self.end_transaction(f"Deleted directory {path}")


import time

class CachedStorageProvider(BaseStorageProvider):
    """A thread-safe, coroutine-safe in-memory caching wrapper for any BaseStorageProvider.

    Caches read-only operations (read, read_bytes, exists, is_dir, list_dir, stat) and
    automatically invalidates them on modifying operations (write, write_bytes, delete, delete_dir).
    """

    def __init__(self, provider: BaseStorageProvider, ttl: int = 0):
        self.provider = provider
        self.ttl = ttl  # TTL in seconds. 0 (or <= 0) means infinite caching.
        self._cache = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, timestamp: float) -> bool:
        if self.ttl <= 0:
            return False
        return (time.time() - timestamp) > self.ttl

    async def read(self, path: str) -> str:
        key = ("read", path)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.read(path)
            self._cache[key] = (value, time.time())
            return value

    async def read_bytes(self, path: str) -> bytes:
        key = ("read_bytes", path)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.read_bytes(path)
            self._cache[key] = (value, time.time())
            return value

    async def exists(self, path: str) -> bool:
        key = ("exists", path)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.exists(path)
            self._cache[key] = (value, time.time())
            return value

    async def is_dir(self, path: str) -> bool:
        key = ("is_dir", path)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.is_dir(path)
            self._cache[key] = (value, time.time())
            return value

    async def list_dir(self, path: str, recursive: bool = False) -> List[str]:
        key = ("list_dir", path, recursive)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.list_dir(path, recursive=recursive)
            self._cache[key] = (value, time.time())
            return value

    async def stat(self, path: str) -> dict:
        key = ("stat", path)
        async with self._lock:
            if key in self._cache:
                value, ts = self._cache[key]
                if not self._is_expired(ts):
                    return value
            
            value = await self.provider.stat(path)
            self._cache[key] = (value, time.time())
            return value

    def _normalize_path(self, path: str) -> str:
        """Normalize a path to be a standard relative POSIX path for key matching."""
        clean = path.replace("\\", "/").strip("/")
        return clean

    def _invalidate_path(self, path: str):
        """Invalidates all cached keys relating to a specific file or directory path."""
        norm_path = self._normalize_path(path)
        
        keys_to_remove = []
        for key in self._cache.keys():
            if len(key) >= 2:
                method, key_path = key[0], key[1]
                norm_key_path = self._normalize_path(key_path)
                
                # Direct match
                if norm_key_path == norm_path:
                    keys_to_remove.append(key)
                    continue
                
                # Check list_dir invalidation: if parent_path is what we modified, list_dir(parent_path) must be invalidated
                if method == "list_dir":
                    if norm_key_path == "" or norm_path == norm_key_path or norm_path.startswith(norm_key_path + "/"):
                        keys_to_remove.append(key)
                        continue
        
        for k in keys_to_remove:
            self._cache.pop(k, None)

    async def write(self, path: str, content: str):
        async with self._lock:
            await self.provider.write(path, content)
            self._invalidate_path(path)

    async def write_bytes(self, path: str, content: bytes):
        async with self._lock:
            await self.provider.write_bytes(path, content)
            self._invalidate_path(path)

    async def delete(self, path: str):
        async with self._lock:
            await self.provider.delete(path)
            self._invalidate_path(path)

    async def delete_dir(self, path: str):
        norm_path = self._normalize_path(path)
        async with self._lock:
            await self.provider.delete_dir(path)
            
            # Remove all cache keys that start with this directory
            keys_to_remove = []
            for key in self._cache.keys():
                if len(key) >= 2:
                    key_path = key[1]
                    norm_key_path = self._normalize_path(key_path)
                    if norm_key_path == norm_path or norm_key_path.startswith(norm_path + "/"):
                        keys_to_remove.append(key)
                        
            for k in keys_to_remove:
                self._cache.pop(k, None)

    async def mkdir(self, path: str, parents: bool = True):
        async with self._lock:
            await self.provider.mkdir(path, parents=parents)
            self._invalidate_path(path)

    async def begin_transaction(self):
        await self.provider.begin_transaction()

    async def end_transaction(self, message: str = "Automated update"):
        await self.provider.end_transaction(message)

    async def cancel_transaction(self):
        await self.provider.cancel_transaction()

    async def close(self):
        async with self._lock:
            self._cache.clear()
            await self.provider.close()

    def clear_cache(self):
        """Manually flush the entire in-memory cache."""
        self._cache.clear()
        logger.info("Storage provider cache flushed.")
