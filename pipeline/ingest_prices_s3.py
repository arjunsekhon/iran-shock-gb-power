"""Upload the price CSVs and the timeline to S3 (Stage 3).

Each price CSV goes into its own subfolder so the Athena CREATE EXTERNAL TABLE
statements (LOCATION = a folder, reads everything in it) map one table to one
file. The timeline lands under raw/events/.
"""

import boto3

from iran_shock.config import S3_BUCKET

s3 = boto3.client("s3")

# price tables — one subfolder per table, matching the Athena DDL LOCATIONs
for name in ("brent", "gb_power", "ttf", "gb_gen_mix"):
    local = f"data/raw/prices/{name}.csv"
    key = f"raw/prices/{name}/{name}.csv"
    s3.upload_file(local, S3_BUCKET, key)
    print(f"uploaded {local} -> s3://{S3_BUCKET}/{key}")

# curated timeline
s3.upload_file(
    "data/epic_fury_timeline.csv", S3_BUCKET, "raw/events/epic_fury_timeline.csv"
)
print(f"uploaded data/epic_fury_timeline.csv -> s3://{S3_BUCKET}/raw/events/")
