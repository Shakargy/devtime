from celery import shared_task


@shared_task
def send_welcome_email(user_id: str) -> None:
    # Runs asynchronously on a Celery worker.
    _deliver(user_id)


def _deliver(user_id: str) -> None:
    return None
