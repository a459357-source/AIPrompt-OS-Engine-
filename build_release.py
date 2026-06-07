#!/usr/bin/env python3
"""Clean personal data, build frontend, package PromptOS exe.

Default: always run scripts/reset_user_data.py first (see .cursor/rules/release-build.mdc).
Never ship api keys, saves, logs, or test artifacts in release zip.

Versioning:
  - Zip name: release/PromptOS-win64-v{APP_VERSION}.zip
  - See RELEASE_VERSIONING.md for release type → command table
  - Default: bump patch, then build
  - --no-bump: keep current APP_VERSION
  - --version X.Y.Z: set explicit MAJOR/MINOR/PATCH
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PromptOS release zip")
    parser.add_argument(
        "--no-bump",
        action="store_true",
        help="不递增版本号，使用当前 APP_VERSION 打包",
    )
    parser.add_argument(
        "--version",
        metavar="X.Y.Z",
        help="指定版本号（大/小版本需显式指定；默认仅 patch+1）",
    )
    return parser.parse_args(argv)


def resolve_release_version(args: argparse.Namespace) -> str:
    if args.version:
        config.parse_app_version(args.version)
        return args.version
    if args.no_bump:
        return config.APP_VERSION
    return config.bump_patch_version(config.APP_VERSION)


def prepare_release_version(args: argparse.Namespace) -> str:
    version = resolve_release_version(args)
    if version != config.APP_VERSION:
        print(f"=== 0. 版本 {config.APP_VERSION} → {version} ===")
        config.persist_app_version(version)
    else:
        print(f"=== 0. 版本 {version}（未递增）===")
    return version


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
        f"prompt_template_adult_extreme.yaml{sep}.",
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
    verify_bundle(exe_dir)
    return exe_dir


def verify_bundle(exe_dir: Path) -> None:
    """Fail fast if PyInstaller did not ship read-only assets under _internal."""
    internal = exe_dir / "_internal"
    required = [
        internal / "engine.yaml",
        internal / "prompt_template.yaml",
        internal / "prompt_template_adult_extreme.yaml",
        internal / "frontend" / "dist" / "index.html",
        internal / "packaging" / "defaults" / "apikey.json",
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        lines = "\n  ".join(str(p) for p in missing)
        raise FileNotFoundError(f"Bundle verification failed — missing:\n  {lines}")


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


def make_zip(exe_dir: Path, version: str) -> Path:
    print("\n=== 5. 生成发布 zip ===")
    RELEASE.mkdir(parents=True, exist_ok=True)
    staging = RELEASE / "_staging"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    shutil.copytree(exe_dir, staging / exe_dir.name)
    ship_files = (
        "启动 PromptOS.bat",
        "停止 PromptOS.bat",
        "PromptOS-用户手册.html",
        "使用说明.txt",
    )
    for name in ship_files:
        src = RELEASE / name
        if src.is_file():
            shutil.copy2(src, staging / name)
            print(f"  bundled {name}")
    shots_dir = RELEASE / "manual-screenshots"
    if shots_dir.is_dir():
        shutil.copytree(shots_dir, staging / "manual-screenshots", dirs_exist_ok=True)
        print(f"  bundled manual-screenshots/ ({len(list(shots_dir.glob('*.png')))} png)")
    zip_base = RELEASE / config.release_zip_basename(version)
    zip_path = zip_base.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    archive = shutil.make_archive(str(zip_base), "zip", root_dir=staging)
    shutil.rmtree(staging, ignore_errors=True)
    print(f"  {archive}")
    return Path(archive)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    version = prepare_release_version(args)
    clean()
    build_frontend()
    exe_dir = build_exe()
    zip_path = make_zip(exe_dir, version)
    print("\n=== 完成 ===")
    print(f"  版本:     v{version}")
    print(f"  程序目录: {exe_dir}")
    print(f"  发布包:   {zip_path}")
    print("  首次运行请在「设置」页填写 DeepSeek API Key")
    return 0


if __name__ == "__main__":
    sys.exit(main())
