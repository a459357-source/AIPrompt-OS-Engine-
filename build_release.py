#!/usr/bin/env python3
"""Clean personal data, build frontend, package PromptOS exe."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "release"
DIST = ROOT / "dist"

AD_HOC_SCRIPTS = [
    "browser_e2e_screenshots.py",
    "simulate_fangzheng_flow.py",
    "verify_browser_flow.py",
    "verify_newstory_controls.py",
    "test_e2e_report.py",
]

OUTPUT_ARTIFACTS = [
    ROOT / "output" / "fangzheng_simulation_report.html",
    ROOT / "output" / "browser_report",
]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"\n>> {' '.join(cmd)}")
    if sys.platform == "win32" and cmd and cmd[0] == "npm":
        cmd = ["npm.cmd", *cmd[1:]]
    subprocess.run(cmd, cwd=cwd or ROOT, check=True, shell=False)


def clean() -> None:
    print("=== 1. 清理个人数据 ===")
    run([sys.executable, str(ROOT / "scripts" / "reset_user_data.py")])

    print("\n=== 2. 删除临时测试脚本与报告 ===")
    for name in AD_HOC_SCRIPTS:
        p = ROOT / name
        if p.exists():
            p.unlink()
            print(f"  removed {name}")
    for p in OUTPUT_ARTIFACTS:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            print(f"  removed {p.name}/")
        elif p.exists():
            p.unlink()
            print(f"  removed {p.name}")

    cache = ROOT / ".pytest_cache"
    if cache.is_dir():
        shutil.rmtree(cache, ignore_errors=True)
        print("  removed .pytest_cache/")


def build_frontend() -> None:
    print("\n=== 3. 构建前端 ===")
    run(["npm", "run", "build"], cwd=ROOT / "frontend")


def build_exe() -> Path:
    print("\n=== 4. 打包 exe (PyInstaller) ===")
    run([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])

    sep = ";" if sys.platform == "win32" else ":"
    add_data = [
        f"frontend/dist{sep}frontend/dist",
        f"packaging/defaults{sep}packaging/defaults",
        f"prompt_template.yaml{sep}.",
        f"engine.yaml{sep}.",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name", "PromptOS",
        "--console",
        f"--distpath={DIST}",
        f"--workpath={ROOT / 'build_pyinstaller'}",
        f"--specpath={ROOT}",
    ]
    for item in add_data:
        cmd.extend(["--add-data", item])
    for pkg in ("engine", "ui"):
        cmd.extend(["--collect-submodules", pkg])
    cmd.extend([
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.workers",
        "--hidden-import", "yaml",
        str(ROOT / "launcher.py"),
    ])
    run(cmd)

    exe_dir = DIST / "PromptOS"
    exe_path = exe_dir / ("PromptOS.exe" if sys.platform == "win32" else "PromptOS")
    if not exe_path.exists():
        raise FileNotFoundError(f"Build failed: {exe_path} not found")
    sanitize_exe_dir(exe_dir)
    return exe_dir


def sanitize_exe_dir(exe_dir: Path) -> None:
    """Remove runtime data/ so release zip never ships someone's apikey or saves."""
    data = exe_dir / "data"
    if data.is_dir():
        shutil.rmtree(data, ignore_errors=True)
        print("  stripped dist/PromptOS/data/ (no personal keys in zip)")
    for name in ("world_pack.yaml", "session_state.yaml"):
        p = exe_dir / name
        if p.exists():
            p.unlink()
            print(f"  stripped dist/PromptOS/{name}")


def make_zip(exe_dir: Path) -> Path:
    print("\n=== 5. 生成发布 zip ===")
    RELEASE.mkdir(parents=True, exist_ok=True)
    zip_base = RELEASE / "PromptOS-win64"
    if zip_base.with_suffix(".zip").exists():
        zip_base.with_suffix(".zip").unlink()
    archive = shutil.make_archive(str(zip_base), "zip", root_dir=exe_dir.parent, base_dir=exe_dir.name)
    print(f"  {archive}")
    return Path(archive)


def main() -> int:
    clean()
    build_frontend()
    exe_dir = build_exe()
    zip_path = make_zip(exe_dir)
    print("\n=== 完成 ===")
    print(f"  程序目录: {exe_dir}")
    print(f"  发布包:   {zip_path}")
    print("  首次运行请在「设置」页填写 DeepSeek API Key")
    return 0


if __name__ == "__main__":
    sys.exit(main())
