from __future__ import annotations

from fastapi import APIRouter, Depends

from video_platform.api.deps import require_token
from video_platform.core.schemas import (
    ModelInstallRequest,
    ModelInstallResponse,
    ModelRecommendationRequest,
    ModelRecommendationResponse,
)
from video_platform.services.model_manager import (
    detect_device_profile,
    get_api_provider,
    get_runtime_mode,
    install_bundle,
    recommend_bundles,
)

router = APIRouter(prefix="/api/v1/models", tags=["models"], dependencies=[Depends(require_token)])


@router.post("/recommend", response_model=ModelRecommendationResponse)
def recommend_models_endpoint(_: ModelRecommendationRequest):
    profile = detect_device_profile()
    bundles, default_bundle = recommend_bundles(profile)

    return ModelRecommendationResponse(
        device=profile,
        bundles=bundles,
        default_bundle=default_bundle,
        runtime_mode=get_runtime_mode(),
        api_provider=get_api_provider(),
    )


@router.post("/install", response_model=ModelInstallResponse)
def install_model_endpoint(payload: ModelInstallRequest):
    try:
        install_path = install_bundle(payload.bundle_name)
        return ModelInstallResponse(
            bundle_name=payload.bundle_name,
            status="installed",
            install_path=install_path,
            message=None,
        )
    except RuntimeError as exc:
        return ModelInstallResponse(
            bundle_name=payload.bundle_name,
            status="skipped",
            install_path="",
            message=str(exc),
        )
