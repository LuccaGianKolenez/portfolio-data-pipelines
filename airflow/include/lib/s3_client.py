import os
import boto3

def get_s3():
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    key = os.getenv("AWS_ACCESS_KEY_ID", "minio")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "minio123")
    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
    )
    return s3, os.getenv("MINIO_BUCKET", "portfolio-bucket")
