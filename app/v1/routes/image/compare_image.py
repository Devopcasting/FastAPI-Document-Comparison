import os
import cv2
import aiofiles
import aiofiles.os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template


router = APIRouter()
IMAGE_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "image"))
BASE_URL = "http://localhost:8030/"

class ImageFileRequest(BaseModel):
    file1_path: str
    file2_path: str
    session_id: str


class ImageDocumentComparator:
    def __init__(self, file_paths) -> None:

        """First Image"""
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_1_name = os.path.basename(self.file_1_path)
        self.file_1_version = self.file_1_path.split('\\')[-2]

        """Second Image"""
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.file_2_name = os.path.basename(self.file_2_path)
        self.file_2_version = self.file_2_path.split('\\')[-2]

        self.session_id = file_paths.session_id

    async def validate_image_document(self):
        """Check if the image path exists"""
        if not os.path.isfile(self.file_1_path.replace("%20", " ")):
            raise HTTPException(status_code=404, detail=f"{self.file_1_path} not found.")
        if not os.path.isfile(self.file_2_path.replace("%20", " ")):
            raise HTTPException(status_code=404, detail=f"{self.file_2_path} not found.")
        
    async def create_workspace(self):
        session_folder = os.path.join(IMAGE_WORKSPACE, self.session_id)
        if not os.path.exists(session_folder):
            await aiofiles.os.makedirs(session_folder)
    
    async def copy_document_to_session_workspace(self):
        try:
            SESSION_PATH = os.path.join(IMAGE_WORKSPACE, self.session_id)
            FILE_1_WORKSPACE = os.path.join(SESSION_PATH, self.file_1_version)
            FILE_2_WORKSPACE = os.path.join(SESSION_PATH, self.file_2_version)
            
            # Create directories asynchronously
            if not os.path.exists(FILE_1_WORKSPACE):
                await aiofiles.os.makedirs(FILE_1_WORKSPACE)
            if not os.path.exists(FILE_2_WORKSPACE):
                await aiofiles.os.makedirs(FILE_2_WORKSPACE)

            
            # Copy files asynchronously
            async with aiofiles.open(self.file_1_path, 'rb') as f1:
                async with aiofiles.open(os.path.join(FILE_1_WORKSPACE, os.path.basename(self.file_1_path)), 'wb') as f1_new:
                    await f1_new.write(await f1.read())

            async with aiofiles.open(self.file_2_path, 'rb') as f2:
                async with aiofiles.open(os.path.join(FILE_2_WORKSPACE, os.path.basename(self.file_2_path)), 'wb') as f2_new:
                    await f2_new.write(await f2.read())
            
            data = [ {
                        "file1": {
                            "file1_name": self.file_1_name,
                            "file1_version": self.file_2_version,
                            "file1_static_path": f"/static/image/{self.session_id}/{self.file_1_version}/{self.file_1_name}"
                        }
                    },
                    {
                        "file2": {
                            "file2_name": self.file_2_name,
                            "file2_version": self.file_2_version,
                            "file2_static_path": f"/static/image/{self.session_id}/{self.file_2_version}/{self.file_2_name}"
                        }
                    }
            ]
            return data
        except Exception as e:
            return False

    async def process_image(self):
        try:
            SESSION_PATH = os.path.join(IMAGE_WORKSPACE, self.session_id)
            image1_path = os.path.join(SESSION_PATH, self.file_1_version, self.file_1_name)
            image2_path = os.path.join(SESSION_PATH, self.file_2_version, self.file_2_name)
            
            # Read Image
            image1 = cv2.imread(image1_path)
            image2 = cv2.imread(image2_path)

            #  Resize Image 2 only if its size doesn't match Image 1
            if image1.shape[:2] != image2.shape[:2]:
                image2_resized = cv2.resize(image2, (image1.shape[1], image1.shape[0]))
            else:
                image2_resized = image2

            # Convert images to grayscale
            gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(image2_resized, cv2.COLOR_BGR2GRAY)

            # Compute absolute difference between the two images
            diff = cv2.absdiff(gray1, gray2)

            # Threshold the difference image
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

            # Find contours of differences
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Create a red box around the contours in image2
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(image2_resized, (x, y), (x+w, y+h), (0, 0, 255), 2)
            
            cv2.imwrite(image2_path, image2_resized)
            return True 
        except Exception as e:
            return False


class HtmlGenerator:
    @staticmethod
    async def generate_result_html_async(session_path, file1, file2, file_1_version, file_2_version, file_1_static_path, file_2_static_path):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, HtmlGenerator.generate_result_html, session_path, file1, file2, file_1_version, file_2_version, file_1_static_path, file_2_static_path)

    @staticmethod
    def generate_result_html(session_path, file1, file2, file_1_version, file_2_version, file_1_static_path, file_2_static_path):
        html_template_str = '''<!DOCTYPE html>
        <html>
            <head>
                <title></title>
                <!-- Bootstrap CSS -->
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet"
        integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
                <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
                <style>
                    body,.badge {
                        font-size: 0.81rem
                    }

                    .table-responsive {
                        overflow-x: unset;
                    }

                    .table-responsive table {
                        width: 100%;
                    }

                    .table-container {
                        display: flex;
                    }

                    .table-container .table-responsive {
                        flex: 0 0 auto;
                        margin-right: 10px;
                    }

                    .square-badge {
                        border-radius: 0;
                    }

                    .divScrollDiv {
                        display: inline-block;
                        width: 100%;
                        border: 1px solid black;
                        height: 98vh;
                        overflow: auto;
                    }

                    .tableNoScroll {
                        overflow: hidden;
                    }

                    .excelFileName {
                        max-width: 20%;
                        white-space: nowrap;
                        overflow: hidden !important;
                        text-overflow: ellipsis;
                        text-align: left;
                    }

                    .badge {
                        padding: .35em .65em !important
                    }

                    .tooltip-inner {
                        max-width: 100%;
                    }

                    .card-header {
                        padding: 0.3rem 0.5rem !important;
                        font-weight: 500;
                    }

                    .card-body {
                        padding: 0.5rem 0.5rem !important;
                    }

                    .headerFileNameCompare {
                        max-width: 80%;
                        white-space: nowrap;
                        overflow: hidden !important;
                        text-overflow: ellipsis;
                    }
                </style>
                <script>
                    $(document).ready(function () {
                        var target_sec = $("#divFixed");
                        $("#divLista").scroll(function () {
                            target_sec.prop("scrollTop", this.scrollTop)
                            .prop("scrollLeft", this.scrollLeft);
                        });

                    var target_first = $("#divLista");

                    $("#divFixed").scroll(function () {
                        target_first.prop("scrollTop", this.scrollTop)
                        .prop("scrollLeft", this.scrollLeft);
                    });
                    });
                </script>
            </head>
            <body>
                <div class="col-lg mx-auto p-1 py-md-1">
                    <div class="container-fluid">
                       <div class="row">
                            <div class="col divScrollDiv border" id="divFixed">
                                <div class="card mt-1">
                                    <div class="card-header d-flex flex-row">
                                        <span class="badge bg-success square-badge excelFileName me-1">{{file_1_version}}</span>
                                        <span class="headerFileNameCompare me-1" title="{{file1}}">{{file1}}</span>
                                    </div>
                                    <div class="card-body">
                                        <div class="table-container">
                                            <div class="table table-responsive">
                                                <!-- Load First Image -->
                                                <img src="{{file_1_static_path}}" class="img-fluid" alt="{{file1}}"
                                        style="height: 100vh; background-size: cover;">
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col divScrollDiv border" id="divLista">
                                <div class="card mt-1">
                                    <div class="card-header d-flex flex-row">
                                        <span class="badge bg-success square-badge excelFileName me-1">{{file_2_version}}</span>
                                        <span class="headerFileNameCompare me-1" title="{{file2}}">{{file2}}</span>
                                    </div>
                                </div>
                                <div class="card-body">
                                    <div class="table-container">
                                        <div class="table table-responsive">
                                            <!--Load Second Image-->
                                            <img src="{{file_2_static_path}}" class="img-fluid" alt="{{file2}}"
                                        style="height: 100vh; background-size: cover;">
                                        </div>
                                    </div>
                                </div>
                            </div>
                       </div> 
                    </div>
                </div>
                <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-MrcW6ZMFYlzcLA8Nl+NtUVF0sA7MsXsP1UyJoMp4YLEuNSfAP+JcXn/tWtIaxVXM"
        crossorigin="anonymous"></script>
            </body>
        </html>'''

        """Render HTML Template"""
        template = Template(html_template_str)
        render_html = template.render(
            file1 = file1,
            file2 = file2,
            file_1_version = file_1_version,
            file_2_version = file_2_version,
            file_1_static_path = file_1_static_path,
            file_2_static_path = file_2_static_path
        )
        with open(f"{session_path}/comparison_result.html", "w") as html_file:
            html_file.write(render_html)


@router.get("/compare_image")
async def generate_url(file_paths: ImageFileRequest, background_tasks: BackgroundTasks):
    comparator = ImageDocumentComparator(file_paths)

    """Validate document"""
    await comparator.validate_image_document()

    """Create Session Workspace"""
    await comparator.create_workspace()

    """Copy images to session workspace"""
    copied_image = await comparator.copy_document_to_session_workspace()
    if not copied_image:
        raise HTTPException(status_code=422, detail=f"Error while copying image")
    
    if not await comparator.process_image():
        raise HTTPException(status_code=422, detail=f"Error while comparing images")


    """Generate HTML"""
    SESSION_PATH = os.path.join(IMAGE_WORKSPACE, comparator.session_id)
    generate_html = HtmlGenerator()
    background_tasks.add_task(generate_html.generate_result_html_async, SESSION_PATH,
                              copied_image[0]['file1']['file1_name'], copied_image[1]['file2']['file2_name'],
                              copied_image[0]['file1']['file1_version'], copied_image[1]['file2']['file2_version'],
                              copied_image[0]['file1']['file1_static_path'], copied_image[1]['file2']['file2_static_path']
                              )
    comparision_result_url = f"{BASE_URL}static/image/{comparator.session_id}/comparison_result.html"

    return JSONResponse(content=({"session_id": comparator.session_id, "result": comparision_result_url}))
