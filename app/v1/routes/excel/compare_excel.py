import os
import aiofiles
import aiofiles.os
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
from jinja2 import Template
import pandas as pd


router = APIRouter()
EXCEL_WORKSPACE = os.path.abspath(os.path.join("app", "v1", "static", "excel"))
BASE_URL = "http://localhost:8030/"

class ExcelFileRequest(BaseModel):
    file1_path: str
    file1_sheet_name: str
    file2_path: str
    file2_sheet_name: str
    session_id: str

class ExcelDocumentComparator:
    def __init__(self, file_paths) -> None:
        """First Document"""
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_1_name = os.path.basename(self.file_1_path)
        self.file_1_version = self.file_1_path.split('\\')[-2]
        self.file1_sheet_name = file_paths.file1_sheet_name
        if not self.file1_sheet_name:
            self.file1_sheet_name = "Sheet1"
        
        """Second Document"""
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.file_2_name = os.path.basename(self.file_2_path)
        self.file_2_version = self.file_2_path.split('\\')[-2]
        self.file2_sheet_name = file_paths.file2_sheet_name
        if not self.file2_sheet_name:
            self.file2_sheet_name = "Sheet1"

        self.session_id = file_paths.session_id
    
    async def validate_excel_document(self):
        """Check if the document exists"""
        if not os.path.isfile(self.file_1_path.replace("%20", " ")):
            raise HTTPException(status_code=404, detail=f"{self.file_1_path} not found.")
        if not os.path.isfile(self.file_2_path.replace("%20", " ")):
            raise HTTPException(status_code=404, detail=f"{self.file_2_path} not found.")
        
        """Check if the sheet name exists"""
        with pd.ExcelFile(self.file_1_path) as xls_file1:
            if not self.file1_sheet_name in xls_file1.sheet_names:
                raise HTTPException(status_code=400, detail=f"Sheet name {self.file1_sheet_name} not found in {self.file_1_path}")
        
        with pd.ExcelFile(self.file_2_path) as xls_file2:
            if not self.file2_sheet_name in xls_file2.sheet_names:
                raise HTTPException(status_code=400, detail=f"Sheet name {self.file2_sheet_name} not found in {self.file_2_path}")

        """Check if the sheet is empty"""
        file1_sheet = pd.read_excel(self.file_1_path, self.file1_sheet_name)
        if file1_sheet.empty:
            raise HTTPException(status_code=400, detail=f"Sheet name {self.file1_sheet_name} in {self.file_1_path} is empty")
        
        file2_sheet = pd.read_excel(self.file_2_path, self.file2_sheet_name)
        if file2_sheet.empty:
            raise HTTPException(status_code=400, detail=f"Sheet name {self.file2_sheet_name} in {self.file_2_path} is empty")

    async def create_workspace(self):
        session_folder = os.path.join(EXCEL_WORKSPACE, self.session_id)
        if not os.path.exists(session_folder):
            await aiofiles.os.makedirs(session_folder)
            
    async def copy_document_to_session_workspace(self):
        try:
            SESSION_PATH = os.path.join(EXCEL_WORKSPACE, self.session_id)
            FILE_1_WORKSPACE = os.path.join(SESSION_PATH, self.file_1_version)
            FILE_2_WORKSPACE = os.path.join(SESSION_PATH, self.file_2_version)

            # Create directories asynchronously
            await aiofiles.os.makedirs(FILE_1_WORKSPACE)
            await aiofiles.os.makedirs(FILE_2_WORKSPACE)

            # Copy files asynchronously
            async with aiofiles.open(self.file_1_path, 'rb') as f1:
                async with aiofiles.open(os.path.join(FILE_1_WORKSPACE, os.path.basename(self.file_1_path)), 'wb') as f1_new:
                    await f1_new.write(await f1.read())

            async with aiofiles.open(self.file_2_path, 'rb') as f2:
                async with aiofiles.open(os.path.join(FILE_2_WORKSPACE, os.path.basename(self.file_2_path)), 'wb') as f2_new:
                    await f2_new.write(await f2.read())
            return True
        except Exception as e:
            return False

    async def process_document(self) -> dict:
        """Panda: Create DataFrame object"""
        df1 = pd.read_excel(self.file_1_path, sheet_name=self.file1_sheet_name, header=None)
        df2 = pd.read_excel(self.file_2_path, sheet_name=self.file2_sheet_name, header=None)

        """
            - Compare the number of rows
            - Put '-' where there is missmatch
            - Replace Nan with '-'
        """
        num_rows_df1 = len(df1)
        num_rows_df2 = len(df2)

        if num_rows_df1 > num_rows_df2:
            diff = num_rows_df1 - num_rows_df2
            nan_rows = pd.DataFrame([['-'] * len(df2.columns)] * diff, columns=df2.columns)
            df2 = pd.concat([df2, nan_rows], ignore_index=True)
        elif num_rows_df1 < num_rows_df2:
            diff = num_rows_df2 - num_rows_df1
            nan_rows = pd.DataFrame([['-'] * len(df1.columns)] * diff, columns=df1.columns)
            df1 = pd.concat([df1, nan_rows], ignore_index=True)

        df1 = df1.fillna('-')
        df2 = df2.fillna('-')

        """
            - Get common headers between df1 and df2
            - Compare df1 and df2 row-by-row
            - Get the index values where df1 and df2 differs
            - Get common indices between df1 and df2
            - Filter df1 and df2 to include only common headers
            - Get differ values
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

        table1 = df1.to_dict(orient='records')
        table2 = df2.to_dict(orient='records')

        return {"data1": table1, "data2": table2, "common_headers_list": common_headers_list,
                "differing_indices": differing_indices, "different_values_df2": different_values_df2}

class HtmlGenerator:
    @staticmethod
    async def generate_result_html_async(session_path, data1, data2, title, file1, file2, file1_sheet_name, file2_sheet_name, file_1_version, file_2_version, differing_indices, different_values_df2):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, HtmlGenerator.generate_result_html, session_path, data1, data2, title, file1, file2, file1_sheet_name, file2_sheet_name, file_1_version, file_2_version, differing_indices, different_values_df2 )

    @staticmethod
    def generate_result_html(session_path, data1, data2, title, file1, file2, file1_sheet_name, file2_sheet_name, file_1_version, file_2_version, differing_indices, different_values_df2):
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
                                                                    <td>{{index}}</td>
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

        """Render HTML Template"""
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
        with open(f"{session_path}/comparison_result.html", "w") as html_file:
            html_file.write(render_html)

@router.get("/compare_excel")
async def generate_url(file_paths: ExcelFileRequest, background_tasks: BackgroundTasks):
    comparator = ExcelDocumentComparator(file_paths)
    
    """Validate Document"""
    await comparator.validate_excel_document()

    """Create Session workspace"""
    await comparator.create_workspace()

    """Copy the documents to session workspace"""
    #await comparator.copy_document_to_session_workspace()
    
    """Process Document"""
    comparision_response = await comparator.process_document()
    
    """Generate HTML"""
    SESSION_PATH = os.path.join(EXCEL_WORKSPACE, comparator.session_id)
    generate_html = HtmlGenerator()
    background_tasks.add_task(generate_html.generate_result_html_async, SESSION_PATH, 
                                comparision_response['data1'], comparision_response['data2'], "Contentverse Excel Document Comparison",
                                comparator.file_1_name, comparator.file_2_name, comparator.file1_sheet_name,
                                comparator.file2_sheet_name, comparator.file_1_version,
                                comparator.file_2_version, comparision_response['differing_indices'], 
                                comparision_response['different_values_df2'] )
    
    # generate_html.generate_result_html(SESSION_PATH, comparision_response['data1'], comparision_response['data2'], "Contentverse Excel Document Comparision",
    #                                    comparator.file_1_name, comparator.file_2_name, comparator.file1_sheet_name,
    #                                    comparator.file2_sheet_name, comparator.file_1_version,
    #                                    comparator.file_2_version, comparision_response['differing_indices'], comparision_response['different_values_df2'])

    comparision_result_url = f"{BASE_URL}static/excel/{comparator.session_id}/comparison_result.html"

    return JSONResponse(content={"session_id": comparator.session_id, "result": comparision_result_url})
