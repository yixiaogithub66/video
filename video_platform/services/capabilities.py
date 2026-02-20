from __future__ import annotations

from video_platform.core.enums import Capability


CAPABILITY_TOOLCHAIN: dict[Capability, list[str]] = {
    Capability.remove_object: [
        "groundingdino_detect",
        "sam2_segment",
        "xmem_track",
        "propainter_inpaint",
        "temporal_smoothing",
    ],
    Capability.replace_object: [
        "target_segment_track",
        "conditional_replace",
        "edge_blend",
        "color_match",
    ],
    Capability.replace_background: [
        "portrait_matting",
        "background_replace_or_generate",
        "lighting_match",
        "shadow_refine",
    ],
    Capability.stylize: [
        "keyframe_stylization",
        "temporal_propagation",
        "anti_flicker_constraint",
    ],
    Capability.color_grade: [
        "lut_curve_suggestion",
        "ffmpeg_color_grading",
        "color_consistency_check",
    ],
    Capability.remove_logo: [
        "logo_text_detect",
        "track_logo",
        "local_inpaint",
        "ocr_residual_check",
    ],
}


CAPABILITY_HINTS: dict[Capability, tuple[str, ...]] = {
    Capability.remove_object: ("remove", "erase", "delete", "去除", "移除"),
    Capability.replace_object: ("replace", "swap", "change object", "替换"),
    Capability.replace_background: ("background", "green screen", "背景", "抠像"),
    Capability.stylize: ("style", "anime", "aesthetic", "风格", "卡通"),
    Capability.color_grade: ("color", "lut", "grading", "调色", "色调"),
    Capability.remove_logo: ("logo", "watermark", "text removal", "去logo", "水印"),
}
