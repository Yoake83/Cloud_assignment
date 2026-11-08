"""Download a model directory from object storage (MODEL_URI = s3://bucket/prefix/)."""
import os
from urllib.parse import urlparse


def download_model(model_uri, dest, endpoint):
    import boto3
    from botocore.config import Config

    u = urlparse(model_uri)
    if u.scheme != "s3":
        raise ValueError(f"MODEL_URI must look like s3://bucket/prefix/, got {model_uri!r}")
    bucket, prefix = u.netloc, u.path.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    s3 = boto3.client(
        "s3", endpoint_url=endpoint, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 5}),
    )  # credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, injected from a Kubernetes Secret
    os.makedirs(dest, exist_ok=True)
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(prefix):]
            if not name or name.endswith("/"):
                continue
            s3.download_file(bucket, obj["Key"], os.path.join(dest, name))
            n += 1
    if n == 0:
        raise RuntimeError(f"no objects found under {model_uri}")
    return n
