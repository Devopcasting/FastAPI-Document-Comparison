import os
import cv2
import fitz
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import shutil
from fastapi.staticfiles import StaticFiles
from app.log_mgmt.docom_log_config import DOCCOMLogging
from PIL import Image
import time

router = APIRouter()
logger = DOCCOMLogging().configure_logger()
PDF_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "pdf"))

class PDFFileRequest(BaseModel):
    file1_path: str
    file2_path: str
    session_id: str

class PDFDocumentComparator:
    def __init__(self, file_paths) -> None:

        """First PDF"""
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_1_name = os.path.basename(self.file_1_path)
        self.file_1_version = self.file_1_path.split('\\')[-2]

        """Second PDF"""
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.file_2_name = os.path.basename(self.file_2_path)
        self.file_2_version = self.file_2_path.split('\\')[-2]

        self.session_id = file_paths.session_id
    
    def create_workspace(self):
        session_folder = os.path.join(PDF_WORKSPACE, self.session_id)
        if not os.path.exists(session_folder):
            os.makedirs(session_folder)
    
    def count_pdf_pages(self, pdf_file: str) -> int:
        try:
            # Open PDF
            pdf_document = fitz.open(pdf_file)
            # Get the number of pages in the PDF
            num_pages = pdf_document.page_count
            pdf_document.close()
            return num_pages
        except Exception as e:
            return 0
        
    def copy_document_to_session_workspace(self):
        try:
            SESSION_PATH = os.path.join(PDF_WORKSPACE, self.session_id)
            FILE_1_WORKSPACE = os.path.join(SESSION_PATH, self.file_1_version)
            FILE_2_WORKSPACE = os.path.join(SESSION_PATH, self.file_2_version)
            
            # Create directories
            os.makedirs(FILE_1_WORKSPACE, exist_ok=True)
            os.makedirs(FILE_2_WORKSPACE, exist_ok=True)

            # Copy files
            shutil.copy(self.file_1_path, FILE_1_WORKSPACE)
            shutil.copy(self.file_2_path, FILE_2_WORKSPACE)

            time.sleep(0.5)
            # Get PDF info
            return {
                "file_1_property": {
                    "file1_name": self.file_1_name,
                    "file1_version": self.file_1_version,
                    "file1_session_path": f"{FILE_1_WORKSPACE}",
                    "file1_path": f"{FILE_1_WORKSPACE}\\{self.file_1_name}",
                    "number_of_pages": self.count_pdf_pages(f"{FILE_1_WORKSPACE}\\{self.file_1_name}")
                },
                "file_2_property": {
                    "file2_name": self.file_2_name,
                    "file2_version": self.file_2_version,
                    "file2_session_path": f"{FILE_2_WORKSPACE}",
                    "file2_path": f"{FILE_2_WORKSPACE}\\{self.file_2_name}",
                    "number_of_pages": self.count_pdf_pages(f"{FILE_2_WORKSPACE}\\{self.file_2_name}")
                }
            }
        except Exception as e:
            logger.error(f"| Copying pdfs to workspace: {e}")
            return False

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
                img.save(image_path,dpi=(500,500))
                converted_image_path_list.append(image_path)
                time.sleep(0.5)
            # Close the PDF file
            pdf_document.close()
            return converted_image_path_list
        except Exception as e:
            logger.error(f"| Spliting and converting PDF: {e}")
            return False

    def compare_pdf_image(self, file1: list, file2: list):
        try:
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
                    logger.error(f"| {file1_filename} not found in {file2_filenames}")
            return True
        except Exception as e:
            logger.error(f"| Extracting filenames: {e}")
            return False

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
                                                    <img src={{i}} class="img-fluid" alt="{{file1}}" style="height: 100vh; background-size: cover;">
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
                                                <img src={{i}} class="img-fluid" alt="{{file2}}" style="height: 100vh; background-size: cover;">
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

        """Render HTML Template"""
        try:
            template = Template(html_template_str)
            render_html = template.render(
                file1 = file1,
                file2 = file2,
                file_1_version = file_1_version,
                file_2_version = file_2_version,
                pdf1_image_list = pdf1_image_list,
                pdf2_image_list = pdf2_image_list
            )

            html_file_path = f"{session_path}/comparison_result.html"
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
            else:
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
        
            time.sleep(5)
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

@router.post("/compare_pdf")
def generate_url(file_paths: PDFFileRequest):
    
    logger.info("| POST request to PDF Document Comparison")
    comparator = PDFDocumentComparator(file_paths)

    """Create Session Workspace"""
    logger.info("| Creating workspace for Image document comparison")
    comparator.create_workspace()

    """Copy images to session workspace"""
    logger.info("| Copying image to session workspace")
    copied_image_info = comparator.copy_document_to_session_workspace()
    if not copied_image_info:
        raise HTTPException(status_code=422, detail=f"Error while copying image")

    """Split, Convert PDF to JPEG"""
    # PDF 1
    split_pdf_1 = comparator.split_convert_pdf_to_jpg(copied_image_info['file_1_property']['file1_path'], copied_image_info['file_1_property']['file1_session_path'])
    # PDF 2
    split_pdf_2 = comparator.split_convert_pdf_to_jpg(copied_image_info['file_2_property']['file2_path'], copied_image_info['file_2_property']['file2_session_path'])


    comparision_result_url = comparator.compare_pdf_image(split_pdf_1, split_pdf_2)
    
    """Generate HTML"""
    logger.info("| Generating Result HTML for Image document")
    SESSION_PATH = os.path.join(PDF_WORKSPACE, comparator.session_id)
    pdf1_image_list = [f"{copied_image_info['file_1_property']['file1_version']}\\page_{i}.jpg" for i in range(1, copied_image_info['file_1_property']['number_of_pages'] + 1)]
    pdf2_image_list = [f"{copied_image_info['file_2_property']['file2_version']}\\page_{i}.jpg" for i in range(1, copied_image_info['file_2_property']['number_of_pages'] + 1)]
    generate_html = HtmlGenerator(comparator)
    
    result = generate_html.generate_result_html(SESSION_PATH,
                                                copied_image_info["file_1_property"]["file1_name"], copied_image_info["file_2_property"]["file2_name"],
                                                 copied_image_info["file_1_property"]["file1_version"], copied_image_info["file_2_property"]["file2_version"],
                                                  pdf1_image_list, pdf2_image_list )

    if not result:
        raise HTTPException(status_code=422, detail=f"Error generating HTML")
    comparision_result_url = f"{result}"

    """Copy Images to user session"""
    # PDF1 Images
    file1_path = "\\".join(comparator.file_1_path.split('\\')[:-1])+"\\"
    for i in range(1, copied_image_info['file_1_property']['number_of_pages'] + 1):
        shutil.copy(f"{SESSION_PATH}\\{copied_image_info['file_1_property']['file1_version']}\\page_{i}.jpg", file1_path)
        time.sleep(0.5)
    # PDF2 Images
    file2_path = "\\".join(comparator.file_2_path.split('\\')[:-1])+"\\"
    for i in range(1, copied_image_info['file_2_property']['number_of_pages'] + 1):
        shutil.copy(f"{SESSION_PATH}\\{copied_image_info['file_2_property']['file2_version']}\\page_{i}.jpg", file2_path)
        time.sleep(0.5)

    """Cleanup session Workspace"""
    SESSION_PATH = os.path.join(PDF_WORKSPACE, comparator.session_id)
    shutil.rmtree(SESSION_PATH)
    logger.info("| Session Workspace Cleanup")
    logger.info("| PDF Document Comparison Completed")
    logger.info(f"| Session ID: {comparator.session_id}")
    logger.info(f"| Comparision Result URL: {comparision_result_url}")
    """Compare PDF images"""
    return JSONResponse(content={"session_id": comparator.session_id, "result": comparision_result_url})