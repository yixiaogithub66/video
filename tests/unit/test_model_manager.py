from video_platform.core.schemas import DeviceProfile
from video_platform.services import model_manager


def test_model_recommendation_uses_remote_bundle_in_api_mode():
    profile = DeviceProfile(
        gpu_name="GPU",
        gpu_count=1,
        gpu_vram_gb=24,
        cuda_available=True,
        cpu_cores=16,
        memory_gb=64,
        disk_free_gb=200,
    )
    bundles, default_bundle = model_manager.recommend_bundles(profile)
    assert any(item.name == "api_remote_bundle" and item.recommended for item in bundles)
    assert default_bundle == "api_remote_bundle"


def test_model_recommendation_prefers_quality_bundle_when_vram_is_high_in_local_mode(monkeypatch):
    profile = DeviceProfile(
        gpu_name="GPU",
        gpu_count=1,
        gpu_vram_gb=24,
        cuda_available=True,
        cpu_cores=16,
        memory_gb=64,
        disk_free_gb=200,
    )
    monkeypatch.setattr(model_manager, "get_runtime_mode", lambda: "local")
    bundles, default_bundle = model_manager.recommend_bundles(profile)
    assert any(item.name == "quality_24g_bundle" and item.recommended for item in bundles)
    assert default_bundle == "quality_24g_bundle"


def test_model_recommendation_falls_back_to_cpu_bundle_without_gpu_in_local_mode(monkeypatch):
    profile = DeviceProfile(
        gpu_name=None,
        gpu_count=0,
        gpu_vram_gb=0,
        cuda_available=False,
        cpu_cores=8,
        memory_gb=16,
        disk_free_gb=80,
    )
    monkeypatch.setattr(model_manager, "get_runtime_mode", lambda: "local")
    _, default_bundle = model_manager.recommend_bundles(profile)
    assert default_bundle == "lite_cpu_bundle"
