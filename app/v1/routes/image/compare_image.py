import os
import uuid
import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import shutil
from fastapi.staticfiles import StaticFiles
from app.log_mgmt.docom_log_config import DOCCOMLogging
from time import sleep

router = APIRouter()
logger = DOCCOMLogging().configure_logger()
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

    def validate_image_document(self):
        """Check if the image path exists"""
        if not os.path.isfile(self.file_1_path.replace("%20", " ")):
            logger.error(f"| {self.file_1_path} not found")
            raise HTTPException(status_code=404, detail=f"{self.file_1_path} not found.")
        if not os.path.isfile(self.file_2_path.replace("%20", " ")):
            logger.error(f"| {self.file_2_path} not found")
            raise HTTPException(status_code=404, detail=f"{self.file_2_path} not found.")
        
    def create_workspace(self):
        session_folder = os.path.join(IMAGE_WORKSPACE, self.session_id)
        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
    
    def copy_document_to_session_workspace(self):
        try:
            SESSION_PATH = os.path.join(IMAGE_WORKSPACE, self.session_id)
            FILE_1_WORKSPACE = os.path.join(SESSION_PATH, self.file_1_version)
            FILE_2_WORKSPACE = os.path.join(SESSION_PATH, self.file_2_version)
            
            # Create directories asynchronously
            if not os.path.exists(FILE_1_WORKSPACE):
                os.makedirs(FILE_1_WORKSPACE)
            if not os.path.exists(FILE_2_WORKSPACE):
                os.makedirs(FILE_2_WORKSPACE)

            
            # Copy files asynchronously
            shutil.copy(self.file_1_path, FILE_1_WORKSPACE)
            shutil.copy(self.file_2_path, FILE_2_WORKSPACE)

            data = [ {
                        "file1": {
                            "file1_name": self.file_1_name,
                            "file1_version": self.file_1_version,
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
            logger.error(f"| Copying images to workspace: {e}")
            return False

    def process_image(self):
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

            """Copy the result images to CVWeb with renamed"""
            image_extention = os.path.splitext(self.file_1_path)[1:][0]
            unique_id_image_1 = uuid.uuid4()
            unique_id_image_1_str = f"{str(unique_id_image_1)}{image_extention}"
            unique_id_image_2 = uuid.uuid4()
            unique_id_image_2_str = f"{str(unique_id_image_2)}{image_extention}"

            shutil.copy(image1_path, f"{'//'.join(self.file_1_path.split('\\')[:-2])}//{unique_id_image_1_str}")
            shutil.copy(image2_path, f"{'//'.join(self.file_1_path.split('\\')[:-2])}//{unique_id_image_2_str}")

            return {"file_1":unique_id_image_1_str, "file_2":unique_id_image_2_str}
        except Exception as e:
            logger.error(f"| Docuemnt Pre-Processing failed: {e}")
            return False


class HtmlGenerator:

    def __init__(self, comparator_instance) -> None:
        self.comparator_instance = comparator_instance

    def generate_result_html(self, session_path, file1, file2, file_1_version, file_2_version, file_1_static_path, file_2_static_path):
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
        try:
            template = Template(html_template_str)
            render_html = template.render(
                file1 = file1,
                file2 = file2,
                file_1_version = file_1_version,
                file_2_version = file_2_version,
                file_1_static_path = file_1_static_path,
                file_2_static_path = file_2_static_path
            )

            html_file_path = f"{session_path}/comparison_result.html"
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
            else:
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
        
            sleep(5)
            """Copy the HTML to CVWeb"""
            destination_path_list = self.comparator_instance.file_1_path.split('\\')
            destination_path_List = self.comparator_instance.file_1_path.split('\\')[:-2]
            destination_path = '\\'.join(destination_path_List)
            shutil.copy(html_file_path, destination_path)
            cvweb_index = destination_path_list.index('CVWeb')
            cvweb_string = '//'.join(destination_path_list[cvweb_index:-2])
            return cvweb_string+"//comparison_result.html"
        except Exception as e:
            logger.error(f"| Generating result HTML failed: {e}")
            return False
    
@router.post("/compare_image")
def generate_url(file_paths: ImageFileRequest):
    logger.info("| POST request to Image Document Comparison")
    comparator = ImageDocumentComparator(file_paths)

    """Validate document"""
    logger.info("| Validating Images")
    comparator.validate_image_document()

    """Create Session Workspace"""
    logger.info("| Creating workspace for Image document comparison")
    comparator.create_workspace()

    """Copy images to session workspace"""
    logger.info("| Copying image to session workspace")
    copied_image = comparator.copy_document_to_session_workspace()
    if not copied_image:
        raise HTTPException(status_code=422, detail=f"Error while copying image")
    
    """Process Image"""
    logger.info("| Start processing image")
    compare_image_result = comparator.process_image()
    if not compare_image_result:
        raise HTTPException(status_code=422, detail=f"Error while comparing images")

    """Generate HTML"""
    logger.info("| Generating Result HTML for Image document")
    SESSION_PATH = os.path.join(IMAGE_WORKSPACE, comparator.session_id)
    generate_html = HtmlGenerator(comparator)
    result = generate_html.generate_result_html(SESSION_PATH,
                              copied_image[0]['file1']['file1_name'], copied_image[1]['file2']['file2_name'],
                              copied_image[0]['file1']['file1_version'], copied_image[1]['file2']['file2_version'],
                              compare_image_result['file_1'], compare_image_result['file_2']
                              )
    if not result:
        raise HTTPException(status_code=422, detail=f"Error generating HTML")
    comparision_result_url = f"{result}"

    """Cleanup session Workspace"""
    SESSION_PATH = os.path.join(IMAGE_WORKSPACE, comparator.session_id)
    shutil.rmtree(SESSION_PATH)
    
    return JSONResponse(content=({"session_id": comparator.session_id, "result": comparision_result_url}))
