import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import pandas as pd
import configparser
import shutil
from app.log_mgmt.docom_log_config import DOCCOMLogging
from time import sleep

# Initialize FastAPI router
router = APIRouter()

# Set the workspace directory for storing excel documents
EXCEL_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "excel"))

# Pydantic model for excel file request
class ExcelFileRequest(BaseModel):
    file1_path: str
    file1_sheet_name: str
    file2_path: str
    file2_sheet_name: str
    session_id: str
    wm_txt_message: str
    wm_img_url: str
    wm_position: str
    wm_txt_fontsize: str
    wm_img_height: str
    wm_img_width: str
    wm_opacity: str
    wm_rotation: str

# Class for excel document comparison
class ExcelDocumentComparator:
    def __init__(self, file_paths: ExcelFileRequest, logger: DOCCOMLogging) -> None:
        # Decode and initialize file paths and session ID
        """First Document"""
        self.file1_path = unquote(r'' + file_paths.file1_path)
        self.file1_name = os.path.basename(self.file1_path)
        self.file1_version = self.file1_path.split('\\')[-2]
        # Check if sheetname is passed
        if file_paths.file1_sheet_name:
            self.file1_sheetname = file_paths.file1_sheet_name
        else:
            # Find the first sheet name
            self.file1_sheetname = pd.ExcelFile(self.file1_path).sheet_names[0]
        
        """Second Document"""
        self.file2_path = unquote(r'' + file_paths.file2_path)
        self.file2_name = os.path.basename(self.file2_path)
        self.file2_version = self.file2_path.split('\\')[-2]
        # Check if sheetname is passed
        if file_paths.file2_sheet_name:
            self.file2_sheetname = file_paths.file2_sheet_name
        else:
            # Find the first sheet name
            self.file2_sheetname = pd.ExcelFile(self.file2_path).sheet_names[0]
        
        self.logger = logger
        self.session_id = file_paths.session_id
    
    def validate_excel_document(self):
        # Validate existence of Excel documents and sheets.
        for file_path, sheet_name in [(self.file1_path, self.file1_sheetname), (self.file2_path, self.file2_sheetname)]:
            # Check if Excel document exists
            if not os.path.isfile(file_path.replace("%20", " ")):
                if self.logger:
                    self.logger.error(f"| {file_path} not found")
                raise HTTPException(status_code=404, detail=f"{file_path} not found.")
        
            # Check if the sheet name exists"""
            with pd.ExcelFile(file_path) as xls_file1:
                if sheet_name not in xls_file1.sheet_names:
                    if self.logger:
                        self.logger.error(f"| Sheet name {sheet_name} not found in {file_path}")
                    raise HTTPException(status_code=400, detail=f"Sheet name {sheet_name} not found in {file_path}")
        
            # Check if the sheet is empty"""
            sheet = pd.read_excel(file_path, sheet_name)
            if sheet.empty:
                if self.logger:
                    self.logger.error(f"| Sheet name {sheet_name} in {file_path} is empty")
                raise HTTPException(status_code=400, detail=f"Sheet name {sheet_name} in {file_path} is empty")

    def create_workspace(self):
        # Create workspace directory for the session if it doesn't exist
        session_folder = os.path.join(EXCEL_WORKSPACE, self.session_id)
        if os.path.exists(session_folder):
            shutil.rmtree(session_folder,ignore_errors=True)
            os.makedirs(session_folder,exist_ok=True)
        os.makedirs(session_folder, exist_ok=True)
        if self.logger:
            self.logger.info(f"| Workspace created for session: {self.session_id}")
            
    def process_document(self) -> dict:
        try:
            # Create DataFrame object
            df1 = pd.read_excel(self.file1_path, sheet_name=self.file1_sheetname, header=None)
            df2 = pd.read_excel(self.file2_path, sheet_name=self.file2_sheetname, header=None)

            # Handle unequal rows
            df1, df2 = self._handle_unequal_rows(df1, df2)

            # Find common_headers_list, common_indices, differing_indices
            common_headers_list, common_indices, differing_indices = self._find_differences(df1, df2)

            # Find different values in df2
            different_values_df2 = self._get_detailed_differences(df1, df2, common_indices)
            
            # Get the table data from the DataFrames
            table1 = df1.to_dict(orient='records')
            table2 = df2.to_dict(orient='records')

            return {"data1": table1, "data2": table2, "common_headers_list": common_headers_list,
                "differing_indices": differing_indices, "different_values_df2": different_values_df2}
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Excel document process failes: {e}")
            raise HTTPException(status_code=500, detail="Error processing Excel document")
    
    def _handle_unequal_rows(self, df1, df2) -> tuple:
        """
        Handles rows with unequal length between DataFrames.

        Args:
            df1: First Excel document DataFrame
            df2: Second Excel document DataFrame

        Returns:
            tuple: A tuple containing the padded DataFrames (df1, df2)
        """
        len_df1 = len(df1)
        len_df2 = len(df2)

        if len_df1 > len_df2:
            diff = len_df1 - len_df2
            nan_rows = pd.DataFrame([['-'] * len(df2.columns)] * diff, columns=df2.columns)
            df2 = pd.concat([df2, nan_rows], ignore_index=True)
        elif len_df1 < len_df2:
            diff = len_df2 - len_df1
            nan_rows = pd.DataFrame([['-'] * len(df1.columns)] * diff, columns=df1.columns)
            df1 = pd.concat([df1, nan_rows], ignore_index=True)

        df1 = df1.fillna('-')
        df2 = df2.fillna('-')
        return (df1, df2)

    def _find_differences(self, df1, df2) -> tuple:
        """
        Find common headers and differing row indices between DataFrames

        Args:
            df1: First Excel document DataFrame
            df2: Second Excel document DataFrame
        
        Returns:
            tuple: A tuple containing the common headers and differing row indices
        """
        common_headers = df1.columns.intersection(df2.columns)
        common_headers_list = list(common_headers)

        comparison = df1.equals(df2)
        if not comparison:
            differing_indices = df1.index[df1.ne(df2).any(axis=1)].tolist()
        else:
            differing_indices = []
        
        common_indices = df1.index.intersection(df2.index)

        df1_common = df1[common_headers]
        df2_common = df2[common_headers]
        common_indices = df1_common.index.intersection(df2_common.index)

        return (common_headers_list, common_indices, differing_indices)

    def _get_detailed_differences(self, df1, df2, common_indices) -> list:
        """
        Extracts detailed information about differences in the second DataFrame.

        Args:
            df1: First Excel document DataFrame
            df2: Second Excel document DataFrame
            common_headers: Common headers between the two DataFrames

        Returns:
            list: A list containing detailed information about differences in df2.
        """
        different_values_df2 = []
        # Iterate through columns of df2
        for column_index, column in enumerate(df2.columns):
            # Check if the column exists in both DataFrames
            if column in df1.columns:
                # Iterate through common indices and compare corresponding values in df1 and df2
                for index in common_indices:
                    # Check if the index exists in both DataFrames
                    if index in df1.index and index in df2.index:
                        # Check if the values differ
                        if df2.loc[index, column] != df1.loc[index, column]:
                            # Append (header_index, cell_index, column, value) to different_values_df2
                            different_values_df2.append((index, column_index, column, df2.loc[index, column]))
            else:
                # If the column exists only in df2, append (header_index, cell_index, column, value) to different_values_df2
                for index in df2.index:
                    if index in df2.index:
                        different_values_df2.append((index, column_index, column, df2.loc[index, column]))
        return different_values_df2

class HtmlGenerator:
    def __init__(self, comparator_instance) -> None:
        self.comparator_instance = comparator_instance

    def generate_result_html(self, session_path, data1, data2, title, file1, file2, file1_sheet_name, file2_sheet_name, file_1_version, file_2_version, differing_indices, different_values_df2):
        # HTML template for comparison result
        html_template_str = '''<!DOCTYPE html>
        <html>
            <head>
                <title>{{title}}</title>
                <!-- Bootstrap CSS -->
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet"
        integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
                <link href="https://icons.getbootstrap.com/assets/font/bootstrap-icons.min.css" rel="stylesheet">
                <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
                <!-- Inline Stylesheet -->
                <style>
                    body,
                    .badge {
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

                    .headerCompareSheetName {
                        max-width: 20%;
                        white-space: nowrap;
                        overflow: hidden !important;
                        text-overflow: ellipsis;
                    }

                    .serial-number-column {
                        width: 25px;
                        background-color:#fff;
                        border: 1px solid #fff;
                    }

                    .hide-header {
                        display: none;
                    }

                    .bi-arrow-bar-right::before {
		                font-size: 1.23rem;
		                font-weight: 500 !important;
		                color: red;
		            }

                    tr td:first-child {
                        border-top: 1px solid #fff;
                        border-left: 1px solid #fff;
                        border-bottom: 1px solid #fff;
                    }

                    .watermark {
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 42px;
                        color: rgba(0, 0, 0, 0.3);
                        pointer-events: none; 
                        z-index: 9999;
                        transform: rotate(-45deg);
                    }

                    .watermarkimg {
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        pointer-events: none;
                        transform: translate(-50%, -50%);
                        z-index: 9999;
                        opacity: 0.5;
                        transform: rotate(-45deg);
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
                        $('[data-toggle="tooltip"]').tooltip({ placement: 'bottom' });
                    });
                </script>
            </head>
            <body>
            <div class="watermark">Document Comparison via Contentverse</div>
            <div class="col-lg mx-auto p-1 py-md-1">
                <div class="container-fluid">
                    <div class="row">
                        <div class="col divScrollDiv border" id="divFixed">
                            <div class="card mt-1">
                                <div class="card-header d-flex flex-row">
                                    <span class="badge bg-success square-badge excelFileName me-1">{{file_1_version}}</span>
                                    <span class="headerFileNameCompare me-1" title="{{file1}}">{{file1}}</span> > 
                                    <span class="headerCompareSheetName ms-1" id="SheetNameExcel1">{{file1_sheet_name}}</span>
                                </div>
                                <div class="card-body">
                                    <div class="table-container">
                                        <div class="table table-responsive">
                                            <table class="table-sm table-bordered">
                                                <thead class="table-dark hide-header">
                                                    <tr>
                                                        <th  class="serial-number-column">#</th>
                                                        {% for column in data1[0].keys() %}
                                                            <th>{{ column }}</th>
                                                        {% endfor %}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {% for index in range(data1 | length) %}
                                                        {% set row = data1[index] %}
                                                        {% if not differing_indices %}
                                                            <tr>
                                                                <td class="tblCompareFirstCoulmn"></td>
                                                                {% for value in row.values() %}
                                                                    <td>{{ value }}</td>
                                                                {% endfor %}
                                                            </tr>
                                                        {% else %}
                                                            <tr>
                                                                {% if loop.index0 in differing_indices %}
                                                                    <td style="background-color: #ffb9b9;">
                                                                        <i class="bi bi-arrow-bar-right"></i>
                                                                    </td>
                                                                {% else %}
                                                                    <td></td>
                                                                {% endif %}
                                                        
                                                                {% for value in row.values() %}
                                                                    <td>{{ value }}</td>
                                                                {% endfor %}
                                                            </tr>
                                                        {% endif %}
                                                    {% endfor %}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col divScrollDiv border" id="divLista">
                            <div class="card mt-1">
                                <div class="card-header d-flex flex-row">
                                    <span class="badge bg-success square-badge excelFileName me-1">{{file_2_version}}</span>
                                    <span class="headerFileNameCompare me-1" title="{{file2}}">{{file2}}</span> >
                                    <span class="headerCompareSheetName ms-1 " id="SheetNameExcel2">{{file2_sheet_name}}</span>
                                </div>
                                <div class="card-body">
                                    <div class="table-container">
                                         <div class="table table-responsive">
                                            <table class="table-sm table-bordered">
                                                <thead class="table-dark hide-header">
                                                    <tr>
                                                        <th class="serial-number-column">#</th>
                                                        {% for column in data2[0].keys() %}
                                                            <th>{{ column }}</th>
                                                        {% endfor %}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {% for index in range(data2 | length) %}
                                                        {% set row = data2[index] %}
                                                        {% if not differing_indices %}
                                                            <tr>
                                                                <td></td>
                                                                {% for column, value in row.items() %}
                                                                    {% set cell_coordinates = (index, loop.index0, column, value) %}
                                                                    {% if cell_coordinates in different_values_df2 %}
                                                                        <td style="background-color: rgb(127, 162, 92);">{{ value }}</td>
                                                                    {% else %}
                                                                        <td>{{ value }}</td>
                                                                    {% endif %}
                                                                {% endfor %}
                                                            </tr>
                                                        {% else %}
                                                            <tr>
                                                                {% if index in differing_indices %}
                                                                    <td style="background-color: #ffb9b9;">
                                                                        <i class="bi bi-arrow-bar-right"></i>
                                                                    </td>
                                                                {% else %}
                                                                    <td></td>
                                                                {% endif %}
                                
                                                                {% for column, value in row.items() %}
                                                                    {% set cell_coordinates = (index, loop.index0, column, value) %}
                                                                    {% if cell_coordinates in different_values_df2 %}
                                                                        <td style="background-color: rgb(127, 162, 92);">{{ value }}</td>
                                                                    {% else %}
                                                                        <td>{{ value }}</td>
                                                                    {% endif %}
                                                                {% endfor %}
                                                            </tr>
                                                        {% endif %}
                                                    {% endfor %}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Bootstrap JS (optional) -->
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-MrcW6ZMFYlzcLA8Nl+NtUVF0sA7MsXsP1UyJoMp4YLEuNSfAP+JcXn/tWtIaxVXM" crossorigin="anonymous"></script>
        </body>
        </html>'''
        try:
            # Render the HTML template with the provided data
            template = Template(html_template_str)
            render_html = template.render(
                title = title,
                data1 = data1,
                data2 = data2,
                file1 = file1,
                file2 = file2,
                file1_sheet_name = file1_sheet_name,
                file2_sheet_name = file2_sheet_name,
                file_1_version = file_1_version,
                file_2_version = file_2_version,
                differing_indices = differing_indices,
                different_values_df2 = different_values_df2
            )

            # Save the rendered HTML to a file
            html_file_path = f"{session_path}/comparison_result.html"
            if os.path.exists(html_file_path):
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)
            else:
                with open(f"{session_path}/comparison_result.html", "w") as html_file:
                    html_file.write(render_html)

            # Pause to ensure file operations are complete
            sleep(5)
            
            
            # Copy the HTML file to the CVWeb destination path
            destination_path_list = self.comparator_instance.file1_path.split('\\')
            destination_path_List = self.comparator_instance.file1_path.split('\\')[:-2]
            destination_path = '\\'.join(destination_path_List)
            shutil.copy(html_file_path, destination_path)
            cvweb_index = destination_path_list.index('CVWeb')
            cvweb_string = '//'.join(destination_path_list[cvweb_index:-2])
            sleep(2)

            # Clean up the session workspace
            if self.comparator_instance.logger:
                self.comparator_instance.logger.info("| Cleaning up session workspace")
            SESSION_PATH = os.path.join(EXCEL_WORKSPACE, self.comparator_instance.session_id)
            shutil.rmtree(SESSION_PATH)

            return cvweb_string+"//comparison_result.html"
        except Exception as e:
            if self.comparator_instance.logger:
                self.comparator_instance.logger.error(f"| Generating result HTML failed: {e}")
            raise HTTPException(status_code=500, detail="Error generating result HTML")

# FastAPI route for comparing excel documents and generating the comparison URL   
@router.post("/compare_excel")
def generate_url(file_paths: ExcelFileRequest):
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
        logger.info("| Received request for excel document comparison")
    comparator = ExcelDocumentComparator(file_paths, logger)
    
    # Validate the provided documents
    if logger:
        logger.info("| Validating Excel Documents")
    comparator.validate_excel_document()

    # Create a workspace for the session
    if logger:
        logger.info("| Creating workspace for session")
    comparator.create_workspace()

    # Process the excel documents and highlight differences
    if logger:
        logger.info("| Start processing Excel document")
    comparision_response = comparator.process_document()
    
    # Generate the result HTML with the comparison
    if logger:
        logger.info("| Generating Result HTML for Excel document")
    session_path = os.path.join(EXCEL_WORKSPACE, comparator.session_id)
    generate_html = HtmlGenerator(comparator)
    result = generate_html.generate_result_html(
        session_path, 
        comparision_response['data1'], 
        comparision_response['data2'], 
        "Contentverse Excel Document Comparison",
        comparator.file1_name, 
        comparator.file2_name, 
        comparator.file1_sheetname,
        comparator.file2_sheetname, 
        comparator.file1_version,
        comparator.file2_version, 
        comparision_response['differing_indices'], 
        comparision_response['different_values_df2'])
    
    if logger:
        logger.info(f"| Result URL: {result}")
    return JSONResponse(content={"session_id": comparator.session_id, "result": result})
        