# FastAPI Document Comparison

This project provides a FastAPI-based solution for comparing documents, supporting Excel, PDFs, and Image file types. It offers a straightforward API for document upload and comparison, allowing users to quickly identify differences between documents of the supported types.

## Features

- **FastAPI Framework**: Built on top of FastAPI, a modern, fast (high-performance), web framework for building APIs with Python 3.12+.
- **Document Comparison**: Enables users to upload Excel, PDFs, and Image documents for comparison.
- **Difference Detection**: Identifies and highlights the differences between uploaded documents.
- **User-friendly API**: Simple and intuitive API endpoints for document upload and comparison.
- **Scalable**: Utilizes the asynchronous capabilities of FastAPI for handling multiple requests efficiently.
- **Customization**: Easy to extend and customize for specific requirements.

## Technology Stack

- **Programming Language**: Python 3.12+
- **Web Framework**: FastAPI
- **Document Processing Libraries**:
  - `openpyxl` for Excel file handling
  - `PyMuPDF` (or `pdf2image`) for PDF processing
  - `Pillow` (PIL) for image processing
- **Asynchronous Processing**: Utilizes Python's `asyncio` for efficient request handling.
- **Deployment**: Can be deployed using Uvicorn or Gunicorn with ASGI support for production environments.

## Requirements

- Python 3.12+
- FastAPI
- Python libraries for document processing (e.g., `openpyxl` for Excel, `PyMuPDF` or `pdf2image` for PDFs, `Pillow` for images)
