"""Upload the partitioned GDELT tree to S3 (Stage 3).

Mirrors data/raw/gdelt/date=YYYY-MM-DD/*.export.CSV to
s3://{S3_BUCKET}/raw/gdelt/date=YYYY-MM-DD/, preserving the Hive partition
layout that Athena's PARTITIONED BY (date string) expects.

Idempotent: an S3 head_object check skips files already uploaded, so re-running
after an interruption only sends what is missing. For a bulk first upload of the
whole tree, `aws s3 sync data/raw/gdelt/ s3://{S3_BUCKET}/raw/gdelt/` is faster
(parallel); this script is the per-file form used by the scheduled-refresh path.
"""

from pathlib import Path

import boto3

from iran_shock.config import RAW_DIR, S3_BUCKET

s3 = boto3.client("s3")


def already_uploaded(key: str) -> bool:
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except s3.exceptions.ClientError:
        return False


uploaded = skipped = 0
for path in sorted(Path(RAW_DIR).glob("date=*/*.export.CSV")):
    rel = path.relative_to(RAW_DIR).as_posix()  # date=YYYY-MM-DD/stamp.export.CSV
    key = f"raw/gdelt/{rel}"
    if already_uploaded(key):
        skipped += 1
        continue
    s3.upload_file(str(path), S3_BUCKET, key)
    uploaded += 1

print(f"uploaded {uploaded}, skipped {skipped} (already present)")
