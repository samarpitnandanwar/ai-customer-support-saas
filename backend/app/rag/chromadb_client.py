import chromadb

# LOCAL CHROMA DATABASE

client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_or_create_collection(
    name="pdf_knowledge"
)