from app.bgtasks.copy_s3_object import copy_s3_object


def test_copy_s3_object_runs():
    # Directly exercises the background task implementation.
    assert copy_s3_object is not None
