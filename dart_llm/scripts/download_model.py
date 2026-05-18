import os
from google.cloud import storage


def download_model():
    model_path = os.getenv("LLM_MODEL_PATH", "/app/model/merged")
    if os.path.exists(f"{model_path}/config.json"):
        print("모델 이미 존재, 다운로드 스킵")
        return

    bucket_name = os.getenv("GCS_BUCKET")
    gcs_prefix = os.getenv("GCS_MODEL_PREFIX", "model/merged")

    if not bucket_name:
        print("GCS_BUCKET 환경변수 없음, 스킵")
        return

    print(f"GCS에서 모델 다운로드: gs://{bucket_name}/{gcs_prefix}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    os.makedirs(model_path, exist_ok=True)

    blobs = list(bucket.list_blobs(prefix=gcs_prefix))
    for i, blob in enumerate(blobs):
        filename = blob.name[len(gcs_prefix):].lstrip("/")
        if not filename:
            continue
        local_path = os.path.join(model_path, filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        print(f"[{i+1}/{len(blobs)}] {filename}")

    print("모델 다운로드 완료")


if __name__ == "__main__":
    download_model()