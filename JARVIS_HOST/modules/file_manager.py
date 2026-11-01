"""
File Manager for Jarvis V2
Handles file and folder operations
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Optional
import subprocess
import time
import re
import unicodedata
from utils.logger import get_logger
from utils.config_manager import get_config
from utils.helpers import format_file_size, get_desktop_path, get_documents_path, get_downloads_path

logger = get_logger()
config = get_config()


class FileManager:
    """Manages file and folder operations"""
    
    def __init__(self):
        self.search_locations = config.get('files.search_locations', [
            str(get_documents_path()),
            str(get_downloads_path()),
            str(get_desktop_path())
        ])
        self.max_results = config.get('files.max_search_results', 50)
        self.search_timeout = max(1, int(config.get('files.search_timeout', 30)))
        self.search_all_fixed_drives = bool(config.get('files.search_all_fixed_drives', True))
        self.excluded_directories = {
            'appdata', 'windows', 'program files', 'program files (x86)',
            'programdata', 'windowsapps', '$recycle.bin',
            'system volume information', 'recovery', 'perflogs',
            'node_modules', '.git', '.venv', 'venv', '__pycache__',
            '.cache', '.gradle', '.npm', '.nuget', 'winsxs', 'temp'
        }
    
    def open_file(self, filepath: str) -> Dict[str, any]:
        """
        Open a file or folder with default application
        """
        try:
            path = Path(filepath)
            
            if not path.exists():
                # Try to resolve common locations
                resolved_path = self._resolve_path(filepath)
                if resolved_path:
                    path = resolved_path
                else:
                    return {
                        'success': False,
                        'message': f"File or folder not found: {filepath}"
                    }
            
            logger.info(f"Opening: {path}")
            
            # Open with default application
            os.startfile(str(path))
            
            return {
                'success': True,
                'message': f"Opened {path.name}"
            }
            
        except Exception as e:
            logger.error(f"Error opening file: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def _local_search_roots(self, location: Optional[str] = None) -> List[Path]:
        """Return user profile first, then configured roots and fixed local disks."""
        candidates = [Path(location).expanduser()] if location else [
            Path.home(),
            *[Path(item).expanduser() for item in self.search_locations],
        ]
        if location is None and self.search_all_fixed_drives and os.name == "nt":
            try:
                import ctypes
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    root = Path(letter + ":\\")
                    if root.exists() and ctypes.windll.kernel32.GetDriveTypeW(str(root)) == 3:
                        candidates.append(root)
            except Exception as exc:
                logger.warning("Yerel disk listesi alınamadı: " + str(exc))

        roots = []
        seen = set()
        for item in candidates:
            try:
                path = item.resolve()
            except (OSError, RuntimeError):
                continue
            key = os.path.normcase(str(path))
            if key not in seen and path.is_dir():
                roots.append(path)
                seen.add(key)
        return roots

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        value = str(value or "").casefold().replace("ı", "i")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return " ".join(value.split())

    def find_files(self, query: str, location: Optional[str] = None,
                   file_type: Optional[str] = None) -> Dict[str, any]:
        """Search local files first, with bounded traversal and system-folder exclusions."""
        try:
            query_text = self._normalize_search_text(query)
            if not query_text:
                return {
                    'success': False, 'files': [],
                    'message': 'Dosya aramak için bir ad veya anahtar kelime belirt.'
                }

            logger.info("Yerel dosya araması başlatıldı: " + str(query))
            roots = self._local_search_roots(location)
            deadline = time.monotonic() + self.search_timeout
            results = []
            seen_paths = set()
            covered_roots = set()
            timed_out = False
            truncated = False

            for search_root in roots:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break

                root_key = os.path.normcase(str(search_root))
                if any(root_key == parent or root_key.startswith(parent + os.sep)
                       for parent in covered_roots):
                    continue

                for root, dirs, files in os.walk(
                    str(search_root), topdown=True, followlinks=False,
                    onerror=lambda exc: logger.debug("Dosya arama erişimi atlandı: " + str(exc))
                ):
                    current_key = os.path.normcase(str(Path(root).resolve()))
                    if current_key in covered_roots:
                        dirs[:] = []
                        continue

                    if time.monotonic() >= deadline:
                        timed_out = True
                        break

                    dirs[:] = sorted(
                        (
                            name for name in dirs
                            if name.casefold() not in self.excluded_directories
                            and not name.startswith('.')
                        ),
                        key=lambda name: (
                            0 if name.casefold() in {'stagepulse', 'projects', 'documents', 'desktop', 'downloads'} else 1,
                            name.casefold()
                        )
                    )

                    for filename in files:
                        if not self._matches_query(filename, query_text, file_type):
                            continue
                        filepath = Path(root) / filename
                        try:
                            canonical = os.path.normcase(str(filepath.resolve()))
                            if canonical in seen_paths or not filepath.is_file():
                                continue
                            stat = filepath.stat()
                            seen_paths.add(canonical)
                            results.append({
                                'name': filename,
                                'path': str(filepath.resolve()),
                                'size': format_file_size(stat.st_size),
                                'size_bytes': stat.st_size,
                                'modified': stat.st_mtime,
                            })
                        except (OSError, PermissionError, RuntimeError):
                            continue

                        if len(results) >= self.max_results:
                            truncated = True
                            break

                    if truncated:
                        break

                covered_roots.add(root_key)
                if timed_out or truncated:
                    break

            results.sort(key=lambda item: item['modified'], reverse=True)
            logger.info(f"Yerel aramada {len(results)} dosya bulundu.")
            return {
                'success': True,
                'files': results,
                'count': len(results),
                'truncated': truncated,
                'timed_out': timed_out,
                'searched_roots': [str(path) for path in roots],
            }

        except Exception as e:
            logger.error("Yerel dosya araması başarısız: " + str(e))
            return {
                'success': False, 'files': [],
                'message': "Yerel dosya araması başarısız: " + str(e)
            }
    
    def create_folder(self, name: str, location: Optional[str] = None) -> Dict[str, any]:
        """
        Create a new folder
        """
        try:
            if location:
                folder_path = Path(location) / name
            else:
                # Default to Documents
                folder_path = get_documents_path() / name
            
            logger.info(f"Creating folder: {folder_path}")
            
            if folder_path.exists():
                return {
                    'success': False,
                    'message': f"Folder already exists: {name}"
                }
            
            folder_path.mkdir(parents=True, exist_ok=False)
            
            return {
                'success': True,
                'path': str(folder_path),
                'message': f"Folder created: {name}"
            }
            
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def delete_file(self, filepath: str) -> Dict[str, any]:
        """
        Delete a file or folder
        """
        try:
            path = Path(filepath)
            
            if not path.exists():
                return {
                    'success': False,
                    'message': f"File or folder not found: {filepath}"
                }
            
            logger.info(f"Deleting: {path}")
            
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            
            return {
                'success': True,
                'message': f"Deleted: {path.name}"
            }
            
        except Exception as e:
            logger.error(f"Error deleting: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def move_file(self, source: str, destination: str) -> Dict[str, any]:
        """
        Move a file or folder
        """
        try:
            src_path = Path(source)
            dst_path = Path(destination)
            
            if not src_path.exists():
                return {
                    'success': False,
                    'message': f"Source not found: {source}"
                }
            
            logger.info(f"Moving {src_path} to {dst_path}")
            
            shutil.move(str(src_path), str(dst_path))
            
            return {
                'success': True,
                'message': f"Moved {src_path.name} to {dst_path}"
            }
            
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def copy_file(self, source: str, destination: str) -> Dict[str, any]:
        """
        Copy a file or folder
        """
        try:
            src_path = Path(source)
            dst_path = Path(destination)
            
            if not src_path.exists():
                return {
                    'success': False,
                    'message': f"Source not found: {source}"
                }
            
            logger.info(f"Copying {src_path} to {dst_path}")
            
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
            else:
                shutil.copy2(str(src_path), str(dst_path))
            
            return {
                'success': True,
                'message': f"Copied {src_path.name} to {dst_path}"
            }
            
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def get_file_info(self, filepath: str) -> Dict[str, any]:
        """
        Get detailed information about a file
        """
        try:
            path = Path(filepath)
            
            if not path.exists():
                return {
                    'success': False,
                    'message': f"File not found: {filepath}"
                }
            
            stat = path.stat()
            
            info = {
                'success': True,
                'name': path.name,
                'path': str(path.absolute()),
                'size': format_file_size(stat.st_size),
                'size_bytes': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'accessed': stat.st_atime,
                'is_directory': path.is_dir(),
                'extension': path.suffix
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def _matches_query(self, filename: str, query: str, file_type: Optional[str]) -> bool:
        """Match Turkish names, separators and multi-word project names."""
        if file_type:
            normalized_type = str(file_type).lower().lstrip('.')
            if Path(filename).suffix.lower().lstrip('.') != normalized_type:
                return False

        target = self._normalize_search_text(Path(filename).stem)
        terms = self._normalize_search_text(query).split()
        return bool(terms) and all(term in target for term in terms)
    
    def _resolve_path(self, path_str: str) -> Optional[Path]:
        """Resolve common path shortcuts"""
        path_lower = path_str.lower()
        
        # Common shortcuts
        shortcuts = {
            'desktop': get_desktop_path(),
            'documents': get_documents_path(),
            'downloads': get_downloads_path(),
            'my documents': get_documents_path(),
        }
        
        for shortcut, actual_path in shortcuts.items():
            if shortcut in path_lower:
                # Replace shortcut with actual path
                resolved = str(actual_path) + path_str[len(shortcut):]
                resolved_path = Path(resolved)
                if resolved_path.exists():
                    return resolved_path
        
        return None
