# Import the necessary modules
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import multiprocessing
import uvicorn
# Import the routers for different document comparison functionalities
from app.v1.routes.excel.properties import router as excel_properties_router
from app.v1.routes.excel.compare_excel import router as excel_comparison_router
from app.v1.routes.image.compare_image import router as image_comparison_router
from app.v1.routes.pdf.compare_pdf import router as pdf_comparison_router


# Define the current API version
API_VERSION = "v1"

def create_app() -> FastAPI:
    """
    Create the main FastAPI application instance

    Returns:
        FastAPI: The FastAPI application instance
    """
    app = FastAPI()

    # Configure CORS middleware
    configure_cors(app)

    # Mount the static file directory
    configure_static_files(app)

    # Register the routers
    register_routers(app, API_VERSION)

    return app
    
def configure_cors(app: FastAPI) -> None:
    """
    Configure CORS (Cross-Origin Resource Sharing) middleware
    to allow cross-origin requests from the specified origin

    Args:
        app (FastAPI): The FastAPI application instance
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def configure_static_files(app: FastAPI) -> None:
    """
    Configure static file directory to be served at the /static endpoint

    Args:
        app (FastAPI): The FastAPI application instance
    """
    app.mount("/static", StaticFiles(directory=r"app\v1\static"), name="static")

def register_routers(app: FastAPI, api_version: str):
    """
    Register the routers for different document comparison functionalities

    Args:
        app (FastAPI): The FastAPI application instance
        api_version (str): The API version
    """
    app.include_router(excel_comparison_router, prefix=f"/api/{api_version}")
    app.include_router(excel_properties_router, prefix=f"/api/{api_version}")
    app.include_router(image_comparison_router, prefix=f"/api/{api_version}")
    app.include_router(pdf_comparison_router, prefix=f"/api/{api_version}")
    
# Create the FastAPI application instance
app = create_app()

# Entry point for running the FastAPI application
if __name__ == '__main__':
    # Determine the number of worker processes based on the available CPU cores
    num_cores = multiprocessing.cpu_count()
    num_workers = 2 if num_cores <= 2 else num_cores * 2 + 1

    # Run the FastAPI application using Uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8030, workers=num_workers)