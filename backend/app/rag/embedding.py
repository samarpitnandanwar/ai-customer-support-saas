from sentence_transformers import (
    SentenceTransformer
)

# FREE EMBEDDING MODEL

embedding_model = (
    SentenceTransformer(
        "all-MiniLM-L6-v2"
    )
)

def create_embedding(
    text: str
):

    embedding = embedding_model.encode(
        text
    )

    return embedding.tolist()