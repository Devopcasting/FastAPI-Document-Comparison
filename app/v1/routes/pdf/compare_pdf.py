# app/v1/routes/pdf/compare_pdf.py

import os
import cv2
import fitz # PyMuPDF
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import configparser
import shutil
from fastapi.staticfiles import StaticFiles
from app.log_mgmt.docom_log_config import DOCCOMLogging
from PIL import Image
import time

# Initialize FastAPI router
router = APIRouter()

# Set the workspace directory for storing PDF
PDF_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "pdf"))

# Pydantic model for image file request
class PDFFileRequest(BaseModel):
    file1_path: str
    file2_path: str
    session_id: str

# Class for PDF document comparison
class PDFDocumentComparator:
    def __init__(self, file_paths: PDFFileRequest, logger: DOCCOMLogging) -> None:
        # Decode and initialize file paths and session ID
        """First PDF"""
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_1_name = os.path.basename(self.file_1_path)
        self.file_1_version = self.file_1_path.split('\\')[-2]

        """Second PDF"""
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.file_2_name = os.path.basename(self.file_2_path)
        self.file_2_version = self.file_2_path.split('\\')[-2]

        self.logger = logger
        self.session_id = file_paths.session_id
    
    def create_workspace(self):
        # Create workspace directory for the session if it doesn't exist
        session_folder = os.path.join(PDF_WORKSPACE, self.session_id)
        os.makedirs(session_folder, exist_ok=True)
        if self.logger:
            self.logger.info(f"| Workspace created for session: {self.session_id}")

    def count_pdf_pages(self, pdf_file: str) -> int:
        try:
            # Open PDF and count the number of pages
            pdf_document = fitz.open(pdf_file)
            num_pages = pdf_document.page_count
            pdf_document.close()
            return num_pages
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error counting pages in PDF {pdf_file}: {e}")
            return 0
        
    def copy_document_to_session_workspace(self):
        try:
            # Define session and version-specific paths
            session_path = os.path.join(PDF_WORKSPACE, self.session_id)
            file_1_workspace = os.path.join(session_path, self.file_1_version)
            file_2_workspace = os.path.join(session_path, self.file_2_version)
            
            # Create directories for PDF versions
            os.makedirs(file_1_workspace, exist_ok=True)
            os.makedirs(file_2_workspace, exist_ok=True)

            # Copy PDF files to their respective directories
            shutil.copy(self.file_1_path, file_1_workspace)
            shutil.copy(self.file_2_path, file_2_workspace)

            if self.logger:
                self.logger.info("| Copied PDFs to session workspace")

            # Short delay to ensure file copy completion
            time.sleep(0.5)

            # Return file properties including path and number of pages
            return {
                "file_1_property": {
                    "file1_name": self.file_1_name,
                    "file1_version": self.file_1_version,
                    "file1_session_path": f"{file_1_workspace}",
                    "file1_path": f"{file_1_workspace}\\{self.file_1_name}",
                    "number_of_pages": self.count_pdf_pages(f"{file_1_workspace}\\{self.file_1_name}")
                },
                "file_2_property": {
                    "file2_name": self.file_2_name,
                    "file2_version": self.file_2_version,
                    "file2_session_path": f"{file_2_workspace}",
                    "file2_path": f"{file_2_workspace}\\{self.file_2_name}",
                    "number_of_pages": self.count_pdf_pages(f"{file_2_workspace}\\{self.file_2_name}")
                }
            }
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Copying pdfs to workspace: {e}")
            raise HTTPException(status_code=500, detail="Error copying PDFs to session workspace")

    def split_convert_pdf_to_jpg(self, pdf_file_path: str, output_path: str ):
        try:
            converted_image_path_list = []
            # Open the provided PDF file
            pdf_document = fitz.open(pdf_file_path)
            # Iterate over each page in the PDF
            for page_number in range(len(pdf_document)):
                # Get the page
                page = pdf_document[page_number]

                # Render the page as an image
                image = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))

                # Convert the image to RGB (Pillow expects RGB images)
                img = Image.frombytes("RGB", [image.width, image.height], image.samples)

                # Save the image
                image_path = f"{output_path}\\page_{page_number + 1}.jpg"
                img.save(image_path,dpi=(300,300))
                converted_image_path_list.append(image_path)
                time.sleep(0.5)
            # Close the PDF file
            pdf_document.close()
            return converted_image_path_list
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Spliting and converting PDF: {e}")
            raise HTTPException(status_code=400, detail="Error converting PDFs to images")

    def compare_pdf_image(self, file1: list, file2: list):
        try:
            if self.logger:
                self.logger.info(f"| Comparing pdf images")
            # Extract filenames from each path in l1 and l2
            file1_filenames = [os.path.basename(path) for path in file1]
            file2_filenames = [os.path.basename(path) for path in file2]
            
            for file1_filename in file1_filenames:
                if file1_filename in file2_filenames:
                    file1_index = file1_filenames.index(file1_filename)
                    file2_index = file2_filenames.index(file1_filename)
                    """Read Image"""
                    image1 = cv2.imread(file1[file1_index])
                    image2 = cv2.imread(file2[file2_index])

                    """Convert images to grayscale"""
                    gray1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
                    gray2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
                    """Compute absolute difference between the two images"""
                    diff = cv2.absdiff(gray1, gray2)
                    """Threshold the difference image"""
                    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                    """Find contours of differences"""
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    """Create underlines (draw horizontal lines) on image2"""
                    underline_thickness = 4  # Thickness of underline
                    underline_color = (0, 0, 255)  # Red Color
                    for contour in contours:
                        x, y, w, h = cv2.boundingRect(contour)
                        # Draw a horizontal line (underline) below the contour
                        underline_y = y + h + underline_thickness  # Position the underline just below the contour
                        cv2.line(image2, (x, underline_y), (x + w, underline_y), underline_color,
                                 underline_thickness)
                    
                    cv2.imwrite(file2[file2_index], image2)
                    time.sleep(0.5)
                else:
                    if self.logger:
                        self.logger.error(f"| {file1_filename} not found in {file2_filenames}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Error comparing PDF: {e}")
            raise HTTPException(status_code=500, detail="Error comparing PDF")

class HtmlGenerator:
    def __init__(self, comparator_instance) -> None:
        self.comparator_instance = comparator_instance

    def generate_result_html(self, session_path, file1, file2, file_1_version, file_2_version, pdf1_image_list, pdf2_image_list):
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
                                    {% for i in pdf1_image_list %}
                                        <div class="card-body shadow mb-3">
                                            <div class="table-container">
                                                <div class="table table-responsive">
                                                    <!-- Load Images -->
                                                    <img src={{i}} class="img-fluid" alt="{{file1}}" style="height: 100%; width:100%; background-size: cover;">
                                                </div>
                                            </div>
                                        </div>
                                    {% endfor %}
                                </div>
                            </div>
                            <div class="col divScrollDiv border" id="divLista">
                                <div class="card mt-1">
                                    <div class="card-header d-flex flex-row">
                                        <span class="badge bg-success square-badge excelFileName me-1">{{file_2_version}}</span>
                                        <span class="headerFileNameCompare me-1" title="{{file2}}">{{file2}}</span>
                                    </div>
                                </div>
                                {% for i in pdf2_image_list %}
                                    <div class="card-body shadow mb-3">
                                        <div class="table-container">
                                            <div class="table table-responsive">
                                                <!--Load Images-->
                                                <img src={{i}} class="img-fluid" alt="{{file2}}" style="height: 100%; width:100%; background-size: cover;">
                                            </div>
                                        </div>
                                    </div>
                                {% endfor %}
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
                pdf1_image_list = pdf1_image_list,
                pdf2_image_list = pdf2_image_list
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
            time.sleep(5)

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
            
@router.post("/compare_pdf")
def generate_url(file_paths: PDFFileRequest):
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
            logger.info("| Received request for pdf document comparison")
        # Initialize the comparator
        comparator_instance = PDFDocumentComparator(file_paths, logger)

        # Create a workspace for the session
        if logger:
            logger.info("| Creating workspace for session")
        comparator_instance.create_workspace()

        # Copy PDFs to the session workspace
        if logger:
            logger.info("| Copying pdf to session workspace")
        copied_pdf_info = comparator_instance.copy_document_to_session_workspace()
    
        # Convert PDFs to Images
        if logger:
            logger.info(f"| Spliting and converting PDF to JPG")
        split_pdf_1 = comparator_instance.split_convert_pdf_to_jpg(copied_pdf_info['file_1_property']['file1_path'], copied_pdf_info['file_1_property']['file1_session_path'])
        split_pdf_2 = comparator_instance.split_convert_pdf_to_jpg(copied_pdf_info['file_2_property']['file2_path'], copied_pdf_info['file_2_property']['file2_session_path'])

        # Compare images and highlight differences
        comparator_instance.compare_pdf_image(split_pdf_1, split_pdf_2)
    
        # Generate HTML to display comparison results
        if logger:
            logger.info("| Generating Result HTML for PDF document")
        session_path = os.path.join(PDF_WORKSPACE, comparator_instance.session_id)
        pdf1_image_list = [f"{copied_pdf_info['file_1_property']['file1_version']}\\page_{i}.jpg" for i in range(1, copied_pdf_info['file_1_property']['number_of_pages'] + 1)]
        pdf2_image_list = [f"{copied_pdf_info['file_2_property']['file2_version']}\\page_{i}.jpg" for i in range(1, copied_pdf_info['file_2_property']['number_of_pages'] + 1)]
        generate_html = HtmlGenerator(comparator_instance)
    
        result = generate_html.generate_result_html(
            session_path,
            copied_pdf_info["file_1_property"]["file1_name"], 
            copied_pdf_info["file_2_property"]["file2_name"],
            copied_pdf_info["file_1_property"]["file1_version"], 
            copied_pdf_info["file_2_property"]["file2_version"],
            pdf1_image_list, pdf2_image_list )

        # Copy the images to user session workspace
        file1_path = "\\".join(comparator_instance.file_1_path.split('\\')[:-1])+"\\"
        for i in range(1, copied_pdf_info['file_1_property']['number_of_pages'] + 1):
            shutil.copy(f"{session_path}\\{copied_pdf_info['file_1_property']['file1_version']}\\page_{i}.jpg", file1_path)
            time.sleep(0.5)
        file2_path = "\\".join(comparator_instance.file_2_path.split('\\')[:-1])+"\\"
        for i in range(1, copied_pdf_info['file_2_property']['number_of_pages'] + 1):
            shutil.copy(f"{session_path}\\{copied_pdf_info['file_2_property']['file2_version']}\\page_{i}.jpg", file2_path)
            time.sleep(0.5)

        # Clean up the session workspace
        if logger:
            logger.info("| Cleaning up session workspace")
        shutil.rmtree(session_path)

        # Return the result URL
        if logger:
            logger.info(f"| Result URL: {result}")
        return JSONResponse(content={"session_id": comparator_instance.session_id, "result": result})
    except Exception as e:
        if logger:
            logger.error(f"| Unexpected error during PDF comparison: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error during PDF comparison")