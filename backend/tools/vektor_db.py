from langchain_qdrant.qdrant import QdrantVectorStore
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

embeddings = HuggingFaceEmbeddings(model="google/embeddinggemma-2")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)
# loader = PyPDFLoader(file_path="../creating_files/constitution_oz.pdf")
# doc = loader.load()
# split_doc = splitter.split_documents(documents=doc)
# # print(doc)
# db = QdrantVectorStore.from_documents(
#     url="http://localhost:6333",
#     documents=split_doc,
#     embedding=embeddings,
#     collection_name="test3",
# )
db = QdrantVectorStore.from_existing_collection(
    url="http://localhost:6333",
    embedding=embeddings,
    collection_name="test3",
)
natija = db.similarity_search("O'zbekistonda senzura taqiqlanganmi? Konstitutsiyada bu haqda nima deyilgan?", k=5)
# for i in natija:
#     print(i)
print(natija)
