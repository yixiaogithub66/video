FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Keep base image minimal for local orchestration validation.
# Add ffmpeg/OpenCV system dependencies in a dedicated runtime image when real pipelines are enabled.

COPY pyproject.toml /app/
COPY video_platform /app/video_platform

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

COPY scripts /app/scripts

CMD ["uvicorn", "video_platform.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
