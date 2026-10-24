from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


async def validation_error(_, error):
    # Do not echo untrusted nonfinite inputs or exception objects into JSON.
    detail = [{k: v for k, v in item.items() if k not in {"input", "ctx"}} for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(detail)})
