from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from urllib.parse import unquote
import pandas as pd
import configparser
import os
from app.log_mgmt.docom_log_config import DOCCOMLogging

# Create the FastAPI router for the Excel document properties endpoint
router = APIRouter()

# Define the Pydantic model for the Excel file request body
class ExcelFileRequest(BaseModel):
    file1_path: str
    file2_path: str

# Define the ExcelDocumentProperties class to handle the extraction of Excel document properties
class ExcelDocumentProperties:
    def __init__(self, file_paths: ExcelFileRequest, logger: DOCCOMLogging) -> None:
        """
        Initialize the ExcelDocumentProperties class with the file paths and a logger instance.

        Args:
            file_paths (ExcelFileRequest): The request containing the file paths.
            logger (DOCCOMLogging): The logger instance to use for logging.
        """
        self.file_1_path = unquote(r'' + file_paths.file1_path)
        self.file_2_path = unquote(r'' + file_paths.file2_path)
        self.logger = logger

    def _validate_excel_document(self, file_path: str) -> None:
        """
        Check if the Excel document exists at the specified file path.
        Args:
            file_path (str): The file path to the Excel document.
        Raises:
            HTTPException: If the Excel document is not found.
        """
        if self.logger:
            self.logger.debug(f"| Validating Excel document for file: {file_path}")
        if not os.path.isfile(file_path.replace("%20", " ")):
            if self.logger:
                self.logger.error(f"| Excel document at {file_path} not found")
            raise HTTPException(status_code=404, detail=f"{file_path} not found.")
        
    def _get_excel_doc_properties(self, file_path: str) -> dict:
        """
        Get the properties of an Excel document.
        Args:
            file_path (str): The file path to the Excel document.
        Returns:
            dict: A dictionary containing the properties of the Excel document.
        """
        try:
            if self.logger:
                self.logger.debug(f"| Reading Excel document properties for file: {file_path}")
            # Read the Excel file using pandas
            df = pd.read_excel(file_path, sheet_name=None)

            # Extract properties for the Excel document
            properties = {}
            for idx, (sheet_name, sheet_df) in enumerate(df.items()):
                is_empty = sheet_df.empty
                properties[sheet_name] = {"index": idx, "empty": is_empty}
            if self.logger:
                self.logger.info(f"| Successfully red Excel document properties for file: {file_path}")
            return properties
        except Exception as e:
            if self.logger:
                self.logger.error(f"| Error reading Excel document at {file_path}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error reading Excel file: {str(e)}")
        
    def get_excel_doc_properties(self) -> dict:
        """
        Get the properties of the Excel documents.
        Returns:
            dict: A dictionary containing the properties of both Excel documents.
        """
        # Validate the first Excel document
        self._validate_excel_document(self.file_1_path)

        # Validate the second Excel document
        self._validate_excel_document(self.file_2_path)

        # Get the properties of the first Excel document
        file1_properties = self._get_excel_doc_properties(self.file_1_path)

        # Get the properties of the second Excel document
        file2_properties = self._get_excel_doc_properties(self.file_2_path)
        return {
            'file1_properties': file1_properties,
            'file2_properties': file2_properties
        }
    
@router.post("/excel_properties")
def properties(file_paths: ExcelFileRequest):
    """
    Endpoint to retrieve the properties of two Excel documents.

    Args:
        file_paths (ExcelFileRequest): The request containing the file paths of the two Excel documents.

    Returns:
        JSONResponse: A JSON response containing the properties of the two Excel documents.
    """
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

    # Create an instance of the ExcelDocumentProperties class
    exceldocproperties = ExcelDocumentProperties(file_paths, logger)
    
    # Return the properties of the Excel documents
    if logger:
        logger.info(f"| Processing Excel document properties for files: {file_paths.file1_path} and {file_paths.file2_path}")
    properties = exceldocproperties.get_excel_doc_properties()

    return JSONResponse(content=properties)