"""Package a trained model: deterministic tar.gz, SHA-256 checksum, upload to object storage.

  python training/package.py v1 [--no-upload]
Creates   artifacts/model-<v>.tar.gz   (the GitHub Release asset)
          artifacts/<v>/model.sha256    = SHA-256 of that tar.gz   (also copied to models/<v>/model.sha256)
Uploads   s3://models/<v>/*   (model files, tokenizer, version.json, model.sha256)
"""
import argparse
import gzip
import hashlib
import os
import shutil
import sys
import tarfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))


def make_tarball(model_dir, tar_path):
    names = sorted(n for n in os.listdir(model_dir)
                   if n != "model.sha256" and os.path.isfile(os.path.join(model_dir, n)))
    with open(tar_path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for n in names:
                info = tar.gettarinfo(os.path.join(model_dir, n), arcname=n)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with open(os.path.join(model_dir, n), "rb") as f:
                    tar.addfile(info, f)
    return names


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    model_dir = f"artifacts/{a.version}"
    tar_path = f"artifacts/model-{a.version}.tar.gz"
    names = make_tarball(model_dir, tar_path)
    digest = sha256_file(tar_path)
    line = f"{digest}  model-{a.version}.tar.gz\n"
    with open(os.path.join(model_dir, "model.sha256"), "w", encoding="utf-8") as f:
        f.write(line)
    os.makedirs(f"models/{a.version}", exist_ok=True)
    shutil.copy(os.path.join(model_dir, "model.sha256"), f"models/{a.version}/model.sha256")
    shutil.copy(os.path.join(model_dir, "version.json"), f"models/{a.version}/version.json")
    print(f"packaged {len(names)} files -> {tar_path}\n{line.strip()}")
    if not a.no_upload:
        import s3util

        s3 = s3util.client()
        s3util.init_buckets(s3)
        s3util.put_dir(s3, "models", a.version, model_dir)


if __name__ == "__main__":
    main()
