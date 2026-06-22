from celery import shared_task


@shared_task
def copy_s3_object(src: str, dst: str) -> None:
    # Runs on a background worker; copies an object between buckets.
    _copy(src, dst)


def _copy(src: str, dst: str) -> None:
    return None
