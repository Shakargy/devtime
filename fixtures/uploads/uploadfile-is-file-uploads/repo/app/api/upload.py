from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/api/upload")
async def upload(file: UploadFile):
    contents = await file.read()
    await _store(file.filename, contents)
    return {"stored": file.filename}


async def _store(name: str, data: bytes) -> None:
    return None
