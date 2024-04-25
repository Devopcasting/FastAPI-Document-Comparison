from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
import pandas as pd
import os
from app.log_mgmt.docom_log_config import DOCCOMLogging

router = APIRouter()
logger = DOCCOMLogging().configure_logger()

class ExcelFileRequest(BaseModel):
    file1_path: str
    file2_path: str

class ExcelDocumentProperties:
    def __init__(self, file_paths) -> None:
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_2_path = unquote(r'' + file_paths.file2_path)

    def validate_excel_document(self):
        """Check if the document exists"""
        if not os.path.isfile(self.file_1_path.replace("%20", " ")):
            logger.error(f"| {self.file_1_path} not found")
            raise HTTPException(status_code=404, detail=f"{self.file_1_path} not found.")
        if not os.path.isfile(self.file_2_path.replace("%20", " ")):
            logger.error(f"| {self.file_2_path} not found")
            raise HTTPException(status_code=404, detail=f"{self.file_2_path} not found.")
    
    def get_excel_doc_properties(self):
        """Get properties of Excel documents"""
        try:
            # Read the Excel files using pandas
            df1 = pd.read_excel(self.file_1_path, sheet_name=None)
            df2 = pd.read_excel(self.file_2_path, sheet_name=None)

            # Extract properties for file1
            file1_properties = {}
            for idx, (sheet_name, sheet_df) in enumerate(df1.items()):
                is_empty = sheet_df.empty
                file1_properties[sheet_name] = {"index": idx, "empty": is_empty}

            # Extract properties for file2
            file2_properties = {}
            for idx, (sheet_name, sheet_df) in enumerate(df2.items()):
                is_empty = sheet_df.empty
                file2_properties[sheet_name] = {"index": idx, "empty": is_empty}

            return {
                'file1_properties': file1_properties,
                'file2_properties': file2_properties
            }
        except Exception as e:
            logger.error(f"| Error reading Excel files: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error reading Excel files: {str(e)}")

@router.post("/excel_properties")
def properties(file_paths: ExcelFileRequest):
    logger.info("| POST request to Excel document properties")
    exceldocproperties = ExcelDocumentProperties(file_paths)

    """Validate Document"""
    logger.info("| Validating Excel Documents")
    exceldocproperties.validate_excel_document()

    """Get the Properties"""
    logger.info("| Get Excel Document properties")
    properties = exceldocproperties.get_excel_doc_properties()

    return JSONResponse(content=properties)