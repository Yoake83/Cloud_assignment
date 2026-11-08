"""Tiny S3 helper for SeaweedFS (boto3). Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."""
import argparse
import os
import sys


def client(endpoint=None):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint or os.environ.get("S3_ENDPOINT", "http://localhost:8333"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 5}),
    )


def get_bytes(s3, bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def get_text(s3, bucket, key):
    return get_bytes(s3, bucket, key).decode("utf-8")


def put_bytes(s3, bucket, key, data):
    s3.put_object(Bucket=bucket, Key=key, Body=data)


def exists(s3, bucket, key):
    from botocore.exceptions import ClientError

    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False


def list_keys(s3, bucket, prefix):
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", [])]
    return sorted(keys)


def init_buckets(s3, names=("datasets", "models")):
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    for n in names:
        if n not in existing:
            s3.create_bucket(Bucket=n)
            print("created bucket", n)
        else:
            print("bucket exists:", n)


def put_dir(s3, bucket, prefix, directory):
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                put_bytes(s3, bucket, f"{prefix.rstrip('/')}/{name}", f.read())
            print(f"uploaded s3://{bucket}/{prefix.rstrip('/')}/{name}")


def get_prefix(s3, bucket, prefix, directory):
    os.makedirs(directory, exist_ok=True)
    for key in list_keys(s3, bucket, prefix):
        name = key[len(prefix):].lstrip("/")
        if not name:
            continue
        with open(os.path.join(directory, name), "wb") as f:
            f.write(get_bytes(s3, bucket, key))
        print(f"downloaded s3://{bucket}/{key}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-buckets")
    p = sub.add_parser("put")
    p.add_argument("bucket"), p.add_argument("key"), p.add_argument("file")
    p = sub.add_parser("get")
    p.add_argument("bucket"), p.add_argument("key"), p.add_argument("file")
    p = sub.add_parser("put-dir")
    p.add_argument("bucket"), p.add_argument("prefix"), p.add_argument("directory")
    p = sub.add_parser("get-prefix")
    p.add_argument("bucket"), p.add_argument("prefix"), p.add_argument("directory")
    a = ap.parse_args()
    s3 = client()
    if a.cmd == "init-buckets":
        init_buckets(s3)
    elif a.cmd == "put":
        with open(a.file, "rb") as f:
            put_bytes(s3, a.bucket, a.key, f.read())
        print(f"uploaded s3://{a.bucket}/{a.key}")
    elif a.cmd == "get":
        with open(a.file, "wb") as f:
            f.write(get_bytes(s3, a.bucket, a.key))
    elif a.cmd == "put-dir":
        put_dir(s3, a.bucket, a.prefix, a.directory)
    elif a.cmd == "get-prefix":
        get_prefix(s3, a.bucket, a.prefix, a.directory)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
