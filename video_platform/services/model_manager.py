from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import psutil

from video_platform.config import settings
from video_platform.core.schemas import DeviceProfile, ModelBundleSpec


BUNDLES = [
    {
        "name": "quality_24g_bundle",
        "min_vram_gb": 24,
        "estimated_time_minutes": 10,
        "download_size_gb": 18.0,
        "quality_tier": "high",
        "enabled_modules": [
            "full_qa",
            "temporal_constraints",
            "high_quality_generation",
        ],
    },
    {
        "name": "balanced_12g_bundle",
        "min_vram_gb": 12,
        "estimated_time_minutes": 14,
        "download_size_gb": 9.5,
        "quality_tier": "balanced",
        "enabled_modules": [
            "core_qa",
            "reduced_batch_generation",
        ],
    },
    {
        "name": "lite_cpu_bundle",
        "min_vram_gb": 0,
        "estimated_time_minutes": 25,
        "download_size_gb": 1.2,
        "quality_tier": "lite",
        "enabled_modules": ["workflow_debug", "basic_tools_only"],
    },
]


def get_runtime_mode() -> str:
    mode = (settings.model_runtime_mode or "").strip().lower()
    return "local" if mode == "local" else "api"


def get_api_provider() -> str:
    return settings.model_api_provider


def _detect_gpu() -> tuple[str | None, int, int, bool]:
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
        if not output:
            return None, 0, 0, False

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        first = lines[0].split(",")
        gpu_name = first[0].strip()
        vram_values = [int(line.split(",")[1].strip()) for line in lines]
        vram_gb = min(vram_values) // 1024
        return gpu_name, len(lines), vram_gb, True
    except Exception:
        return None, 0, 0, False


def detect_device_profile() -> DeviceProfile:
    gpu_name, gpu_count, gpu_vram_gb, cuda_available = _detect_gpu()
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(".")

    return DeviceProfile(
        gpu_name=gpu_name,
        gpu_count=gpu_count,
        gpu_vram_gb=gpu_vram_gb,
        cuda_available=cuda_available,
        cpu_cores=psutil.cpu_count(logical=True) or 1,
        memory_gb=int(vm.total / (1024**3)),
        disk_free_gb=int(disk.free / (1024**3)),
    )


def recommend_bundles(profile: DeviceProfile) -> tuple[list[ModelBundleSpec], str]:
    mode = get_runtime_mode()

    if mode == "api":
        remote = ModelBundleSpec(
            name="api_remote_bundle",
            min_vram_gb=0,
            estimated_time_minutes=6,
            download_size_gb=0.0,
            quality_tier="remote",
            enabled_modules=["remote_multimodal_llm", "remote_video_edit_model"],
            recommended=True,
        )
        return [remote], remote.name

    specs: list[ModelBundleSpec] = []
    best_name = "lite_cpu_bundle"

    for bundle in BUNDLES:
        recommended = profile.gpu_vram_gb >= bundle["min_vram_gb"]
        spec = ModelBundleSpec(
            name=bundle["name"],
            min_vram_gb=bundle["min_vram_gb"],
            estimated_time_minutes=bundle["estimated_time_minutes"],
            download_size_gb=bundle["download_size_gb"],
            quality_tier=bundle["quality_tier"],
            enabled_modules=bundle["enabled_modules"],
            recommended=recommended,
        )
        specs.append(spec)

    for candidate in ("quality_24g_bundle", "balanced_12g_bundle", "lite_cpu_bundle"):
        match = next((item for item in specs if item.name == candidate and item.recommended), None)
        if match is not None:
            best_name = match.name
            break

    if profile.gpu_count == 0:
        best_name = "lite_cpu_bundle"

    return specs, best_name


def install_bundle(bundle_name: str) -> str:
    if get_runtime_mode() != "local":
        raise RuntimeError("Local bundle installation is disabled in API runtime mode.")
    if not settings.allow_local_model_install:
        raise RuntimeError("Local bundle installation is disabled by configuration.")

    target_dir = Path(settings.models_dir) / bundle_name
    target_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "bundle_name": bundle_name,
        "status": "installed",
        "source": "local-placeholder",
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return os.fspath(target_dir.resolve())
