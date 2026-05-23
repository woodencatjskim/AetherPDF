"""
GitHub Releases based update support for AetherPDF.

This module keeps update checks serverless by using the public GitHub Releases
API and a release asset named AetherPDF.exe.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import APP_NAME, APP_VERSION, GITHUB_RELEASES_API


ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class UpdateInfo:
    """Metadata for an available GitHub release update."""

    current_version: str
    latest_version: str
    release_url: str
    asset_url: str
    asset_name: str


class UpdateService:
    """Utility methods for checking and applying application updates."""

    ASSET_NAME = "AetherPDF.exe"
    USER_AGENT = f"{APP_NAME}/{APP_VERSION}"

    @staticmethod
    def check_for_update() -> Optional[UpdateInfo]:
        """Return update metadata when a newer GitHub release is available."""
        request = Request(
            GITHUB_RELEASES_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": UpdateService.USER_AGENT,
            },
        )

        try:
            with urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

        latest_version = UpdateService._normalize_version(payload.get("tag_name", ""))
        if not latest_version or not UpdateService._is_newer(latest_version, APP_VERSION):
            return None

        asset = UpdateService._find_windows_asset(payload.get("assets", []))
        if not asset:
            return None

        return UpdateInfo(
            current_version=APP_VERSION,
            latest_version=latest_version,
            release_url=payload.get("html_url", ""),
            asset_url=asset["browser_download_url"],
            asset_name=asset["name"],
        )

    @staticmethod
    def download_update(info: UpdateInfo, progress: Optional[ProgressCallback] = None) -> str:
        """Download the update executable and return its temporary file path."""
        update_dir = os.path.join(tempfile.gettempdir(), "AetherPDF_update")
        os.makedirs(update_dir, exist_ok=True)
        target_path = os.path.join(update_dir, info.asset_name)

        request = Request(
            info.asset_url,
            headers={"User-Agent": UpdateService.USER_AGENT},
        )

        with urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(target_path, "wb") as file:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    file.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        progress(downloaded, total)

        if os.path.getsize(target_path) == 0:
            raise RuntimeError("Downloaded update file is empty.")

        return target_path

    @staticmethod
    def can_apply_update() -> bool:
        """Return True when running from a packaged executable."""
        return bool(getattr(sys, "frozen", False)) and os.path.isfile(sys.executable)

    @staticmethod
    def launch_update_replacer(downloaded_exe: str) -> None:
        """Start a temporary batch script that replaces this executable and relaunches it."""
        if not UpdateService.can_apply_update():
            raise RuntimeError("Updates can only be applied from the packaged executable.")

        current_exe = os.path.abspath(sys.executable)
        if not os.path.isfile(downloaded_exe):
            raise FileNotFoundError(downloaded_exe)

        backup_exe = UpdateService._next_backup_path(current_exe)
        script_path = os.path.join(tempfile.gettempdir(), "AetherPDF_update", "apply_update.bat")
        os.makedirs(os.path.dirname(script_path), exist_ok=True)

        with open(script_path, "w", encoding="utf-8") as script:
            script.write(
                "@echo off\n"
                "setlocal\n"
                f"set \"TARGET={current_exe}\"\n"
                f"set \"UPDATE={os.path.abspath(downloaded_exe)}\"\n"
                f"set \"BACKUP={backup_exe}\"\n"
                "timeout /t 2 /nobreak >nul\n"
                "move /y \"%TARGET%\" \"%BACKUP%\" >nul\n"
                "if errorlevel 1 goto failed\n"
                "copy /y \"%UPDATE%\" \"%TARGET%\" >nul\n"
                "if errorlevel 1 goto restore\n"
                "set PYINSTALLER_RESET_ENVIRONMENT=1\n"
                "start \"\" \"%TARGET%\"\n"
                "exit /b 0\n"
                ":restore\n"
                "move /y \"%BACKUP%\" \"%TARGET%\" >nul\n"
                ":failed\n"
                "start \"\" \"%TARGET%\"\n"
                "exit /b 1\n"
            )

        subprocess.Popen(
            ["cmd", "/c", script_path],
            cwd=os.path.dirname(current_exe),
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

    @staticmethod
    def cleanup_old_backups() -> None:
        """Remove previous update backup executables when possible."""
        if not UpdateService.can_apply_update():
            return

        current_exe = os.path.abspath(sys.executable)
        exe_dir = os.path.dirname(current_exe)
        stem, ext = os.path.splitext(os.path.basename(current_exe))
        for filename in os.listdir(exe_dir):
            if filename.startswith(f"{stem}.old") and filename.endswith(ext):
                try:
                    os.remove(os.path.join(exe_dir, filename))
                except OSError:
                    pass

    @staticmethod
    def _find_windows_asset(assets: list[dict]) -> Optional[dict]:
        """Find the release asset used for Windows self-update."""
        for asset in assets:
            if asset.get("name") == UpdateService.ASSET_NAME and asset.get("browser_download_url"):
                return asset
        return None

    @staticmethod
    def _normalize_version(value: str) -> str:
        """Normalize tags such as v1.2.3 into 1.2.3."""
        match = re.search(r"\d+(?:\.\d+)*", value or "")
        return match.group(0) if match else ""

    @staticmethod
    def _is_newer(candidate: str, current: str) -> bool:
        """Compare dotted numeric versions."""
        return UpdateService._version_tuple(candidate) > UpdateService._version_tuple(current)

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        """Convert a dotted version string into a comparable integer tuple."""
        normalized = UpdateService._normalize_version(value)
        if not normalized:
            return (0,)
        return tuple(int(part) for part in normalized.split("."))

    @staticmethod
    def _next_backup_path(current_exe: str) -> str:
        """Return a unique backup executable path next to the current exe."""
        exe_dir = os.path.dirname(current_exe)
        stem, ext = os.path.splitext(os.path.basename(current_exe))
        timestamp = time.strftime("%Y%m%d%H%M%S")
        return os.path.join(exe_dir, f"{stem}.old-{timestamp}{ext}")
