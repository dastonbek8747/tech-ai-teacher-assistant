from langchain_community.agent_toolkits.file_management import FileManagementToolkit
from langchain_community.document_loaders import (
    CSVLoader,
    JSONLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredExcelLoader,
    UnstructuredPDFLoader,
    UnstructuredURLLoader,
    UnstructuredWordDocumentLoader,
    YoutubeLoader,
)


def read_word_file(file_path: str):
    loader = UnstructuredWordDocumentLoader(file_path)
    doc = loader.load()
    return {"document": doc, "metadate": doc[0].metadata, "file_path": file_path}


def read_excel_file(file_path: str):
    loader = UnstructuredExcelLoader(file_path)
    doc = loader.load()
    return {"document": doc, "metadate": doc[0].metadata, "file_path": file_path}


def read_pdf_file(file_path: str):
    loader = UnstructuredPDFLoader(file_path)
    doc = loader.load()
    return {"document": doc, "metadate": doc[0].metadata, "file_path": file_path}


def read_text_file(file_path: str):
    loader = TextLoader(file_path)
    doc = loader.load()
    return {"document": doc, "metadate": doc[0].metadata, "file_path": file_path}


def read_json_file(file_path: str):
    loader = JSONLoader(file_path)
    doc = loader.load()
    return {"document": doc, "metadate": doc[0].metadata, "file_path": file_path}


file_toolkit = FileManagementToolkit(root_dir="../creating_files")
file_tools = file_toolkit.get_tools()

FILE_MANAGMENT_TOOLS = file_tools + [read_text_file, read_excel_file, read_json_file, read_word_file, read_pdf_file]
