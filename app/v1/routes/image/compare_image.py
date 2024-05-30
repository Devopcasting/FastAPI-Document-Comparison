import os
import uuid
import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import shutil
import configparser
from app.log_mgmt.docom_log_config import DOCCOMLogging
from time import sleep
import numpy as np 

# Initialize FastAPI router
router = APIRouter()

# Set the workspace directory for storing images
IMAGE_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "image"))

# Pydantic model for image file request
class ImageFileRequest(BaseModel):
    file1_path: str
    file2_path: str
    session_id: str

# Class for image document comparison
class ImageDocumentComparator:
    def __init__(self, file_paths: ImageFileRequest, logger: DOCCOMLogging ) -> None:
        # Decode and initialize file paths and session ID
        """First Image"""
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_1_name = os.path.basename(self.file_1_path)
        self.file_1_version = self.file_1_path.split('\\')[-2]

        """Second Image"""
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.file_2_name = os.path.basename(self.file_2_path)
        self.file_2_version = self.file_2_path.split('\\')[-2]

        self.logger = logger
        self.session_id = file_paths.session_id

    def validate_image_document(self):
        # Validate if image files exist
        if not os.path.isfile(self.file_1_path.replace("%20", " ")):
            if self.logger:
                self.logger.error(f"| Image not found: {self.file_1_path}")
            raise HTTPException(status_code=404, detail=f"{self.file_1_path} not found.")
        if not os.path.isfile(self.file_2_path.replace("%20", " ")):
            if self.logger:
                self.logger.error(f"| Image not found: {self.file_2_path}")
            raise HTTPException(status_code=404, detail=f"{self.file_2_path} not found.")
        
    def create_workspace(self):
        # Create workspace directory for the session if it doesn't exist
        session_folder = os.path.join(IMAGE_WORKSPACE, self.session_id)
        os.makedirs(session_folder, exist_ok=True)
        if self.logger:
            self.logger.info(f"| Workspace created for session: {self.session_id}")
    
    def copy_document_to_session_workspace(self):
        try:
            # Create directories for the image versions within the session workspace
            session_path = os.path.join(IMAGE_WORKSPACE, self.session_id)
            file_1_workspace = os.path.join(session_path, self.file_1_version)
            file_2_workspace = os.path.join(session_path, self.file_2_version)
            
            # Create session workspace folder
            os.makedirs(file_1_workspace, exist_ok=True)
            os.makedirs(file_2_workspace, exist_ok=True)
            
            # Copy images to the session workspace
            shutil.copy(self.file_1_path, file_1_workspace)
            shutil.copy(self.file_2_path, file_2_workspace)

            if self.logger:
                self.logger.info(f"| Images copied to workspace for session: {self.session_id}")

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
            if self.logger:
                self.logger.error(f"| Error copying images to workspace: {e}")
            raise HTTPException(status_code=500, detail="Error copying images to workspace")

    def process_image(self):
        try:
            # Paths for images in the session workspace
            SESSION_PATH = os.path.join(IMAGE_WORKSPACE, self.session_id)
            image1_path = os.path.join(SESSION_PATH, self.file_1_version, self.file_1_name)
            image2_path = os.path.join(SESSION_PATH, self.file_2_version, self.file_2_name)
            
            # Read Image
            image1 = cv2.imread(image1_path)
            image2 = cv2.imread(image2_path)

            # Resize image2 if dimensions do not match
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

            # Draw bounding boxes around differences in image2
            red_color = (51, 51, 255)
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                # Create a green rectangle with opacity
                opacity = 0.3
                overlay = image2_resized.copy()
                cv2.rectangle(overlay, (x, y), (x+w, y+h), red_color, cv2.FILLED)
                cv2.addWeighted(overlay, opacity, image2_resized, 1 - opacity, 0, image2_resized)
            cv2.imwrite(image2_path, image2_resized)

            # Generate unique IDs for the processed images
            image_extention = os.path.splitext(self.file_1_path)[1:][0]
            unique_id_image_1 = uuid.uuid4()
            unique_id_image_1_str = f"{str(unique_id_image_1)}{image_extention}"
            unique_id_image_2 = uuid.uuid4()
            unique_id_image_2_str = f"{str(unique_id_image_2)}{image_extention}"

            # Copy processed images to base path
            shutil.copy(image1_path, f"{'//'.join(self.file_1_path.split('\\')[:-2])}//{unique_id_image_1_str}")
            shutil.copy(image2_path, f"{'//'.join(self.file_1_path.split('\\')[:-2])}//{unique_id_image_2_str}")

            if self.logger:
                self.logger.info(f"| Processed images for session: {self.session_id}")

            return {"file_1":unique_id_image_1_str, "file_2":unique_id_image_2_str}
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Docuemnt Pre-Processing failed: {e}")
            raise HTTPException(status_code=500, detail="Error processing images")


class HtmlGenerator:

    def __init__(self, comparator_instance) -> None:
        self.comparator_instance = comparator_instance

    def generate_result_html(self, session_path, file1, file2, file_1_version, file_2_version, file_1_static_path, file_2_static_path):
        # HTML template for comparison result
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
                                        style="height: 100%; width: 100%; background-size: cover;">
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
                                        style="height: 100%; width: 100%; background-size: cover;">
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

        try:
            # Render the HTML template with the provided data
            template = Template(html_template_str)
            render_html = template.render(
                file1 = file1,
                file2 = file2,
                file_1_version = file_1_version,
                file_2_version = file_2_version,
                file_1_static_path = file_1_static_path,
                file_2_static_path = file_2_static_path
            )

            # Save the rendered HTML to a file
            html_file_path = f"{session_path}/comparison_result.html"
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
            else:
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)

            # Pause to ensure file operations are complete
            sleep(5)

            # Copy the HTML file to the CVWeb destination path
            destination_path_list = self.comparator_instance.file_1_path.split('\\')
            destination_path_List = self.comparator_instance.file_1_path.split('\\')[:-2]
            destination_path = '\\'.join(destination_path_List)
            shutil.copy(html_file_path, destination_path)
            cvweb_index = destination_path_list.index('CVWeb')
            cvweb_string = '//'.join(destination_path_list[cvweb_index:-2])
            return cvweb_string+"//comparison_result.html"
        except Exception as e:
            if self.comparator_instance.logger:
                self.comparator_instance.logger.error(f"| Generating result HTML failed: {e}")
            raise HTTPException(status_code=500, detail="Error generating result HTML")
        
# FastAPI route for comparing images and generating the comparison URL   
@router.post("/compare_image")
def generate_url(file_paths: ImageFileRequest):
    try:
        # Read configuration from the configuration file
        config = configparser.ConfigParser(allow_no_value=True)
        configuration_file_path = os.path.abspath(os.path.join("config","configuration.ini"))
        config.read(rf"{configuration_file_path}")
        logging_enabled = config.get('Logging', 'logging_enabled')
    
        # Configure the logger if logging is enabled
        if logging_enabled == "on":
            logger = DOCCOMLogging().configure_logger()
        else:
            # Set logger to None if logging is disabled
            logger = None

        if logger:
            logger.info("| Received request for image document comparison")
        comparator = ImageDocumentComparator(file_paths, logger)

        # Validate the provided images
        if logger:
            logger.info("| Validating Images")
        comparator.validate_image_document()

        # Create a workspace for the session
        if logger:
            logger.info("| Creating workspace for session")
        comparator.create_workspace()

        # Copy the images to the session workspace
        if logger:
            logger.info("| Copying images to session workspace")
        copied_image = comparator.copy_document_to_session_workspace()
    
        # Process the images and highlight differences
        if logger:
            logger.info("| Processing images for differences")
        compare_image_result = comparator.process_image()
    
        # Generate the result HTML with the comparison
        if logger:
            logger.info("| Generating Result HTML for Image document")
        session_path = os.path.join(IMAGE_WORKSPACE, comparator.session_id)
        generate_html = HtmlGenerator(comparator)
        result = generate_html.generate_result_html(
            session_path,
            copied_image[0]['file1']['file1_name'],
            copied_image[1]['file2']['file2_name'],
            copied_image[0]['file1']['file1_version'], 
            copied_image[1]['file2']['file2_version'],
            compare_image_result['file_1'], 
            compare_image_result['file_2']
            )

        # Clean up the session workspace
        if logger:
            logger.info("| Cleaning up session workspace")
        shutil.rmtree(session_path)

        # Return the result URL
        if logger:
            logger.info(f"| Result URL: {result}")    
        return JSONResponse(content=({"session_id": comparator.session_id, "result": result}))
    except Exception as e:
        if logger:
            logger.error(f"| Unexpected error during PDF comparison: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error during Image comparison")
