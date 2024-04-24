from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.v1.routes.excel.compare_excel import router as excel_doc_endpoint
from app.v1.routes.excel.properties import router as excel_doc_properties
from app.v1.routes.image.compare_image import router as image_doc_endpoint
from app.v1.routes.cleanup.session_cleanup import router as cleanup_session

app = FastAPI()

origins = ["http://localhost:8065"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=r"app\v1\static"), name="static")

app.include_router(excel_doc_endpoint, prefix="/v1")
app.include_router(excel_doc_properties, prefix="/v1")
app.include_router(image_doc_endpoint, prefix="/v1")
app.include_router(cleanup_session, prefix="/v1")

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8030, reload=True, workers=2)