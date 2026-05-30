from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from fastapi import (
    UploadFile,
    File,
    Form,
)

import shutil
import uuid
import os

from pypdf import PdfReader

from sqlalchemy.orm import Session

import ollama

from app.database import (
    engine,
    SessionLocal,
    Base
)

from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message

from app.auth import (
    hash_password,
    verify_password,
    create_access_token
)

from app.rag.embedding import (
    create_embedding
)

from app.rag.chromadb_client import (
    collection
)

from app.rag.chunker import (
    chunk_text
)

from app.rag.ocr import (
    extract_text_from_scanned_pdf
)

# CREATE DATABASE TABLES

Base.metadata.create_all(bind=engine)

# CREATE UPLOADS FOLDER

os.makedirs(
    "uploads",
    exist_ok=True
)

# FASTAPI APP

app = FastAPI()

# CHAT SPECIFIC MEMORY

conversation_contexts = {}

# CORS

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)

# DATABASE SESSION

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()

# HOME

@app.get("/")
async def home():

    return {
        "message":
        "AI Backend Running"
    }

# REGISTER

@app.post("/register")
async def register(
    data: dict
):

    db: Session = SessionLocal()

    try:

        if not data.get("name"):

            return {
                "error":
                "Name required"
            }

        if not data.get("email"):

            return {
                "error":
                "Email required"
            }

        if not data.get("password"):

            return {
                "error":
                "Password required"
            }

        if len(data["password"]) < 6:

            return {
                "error":
                "Password must be at least 6 characters"
            }

        if len(data["password"]) > 50:

            return {
                "error":
                "Password too long"
            }

        existing_user = db.query(
            User
        ).filter(
            User.email ==
            data["email"]
        ).first()

        if existing_user:

            return {
                "error":
                "Email already exists"
            }

        hashed_password = hash_password(
            data["password"]
        )

        new_user = User(

            name=data["name"],

            email=data["email"],

            password=hashed_password
        )

        db.add(new_user)

        db.commit()

        db.refresh(new_user)

        return {
            "message":
            "User registered successfully"
        }

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# LOGIN

@app.post("/login")
async def login(
    data: dict
):

    db: Session = SessionLocal()

    try:

        user = db.query(
            User
        ).filter(
            User.email ==
            data["email"]
        ).first()

        if not user:

            return {
                "error":
                "Invalid email"
            }

        valid_password = verify_password(
            data["password"],
            user.password
        )

        if not valid_password:

            return {
                "error":
                "Invalid password"
            }

        token = create_access_token({
            "sub": user.email
        })

        return {

            "access_token":
            token,

            "token_type":
            "bearer",

            "user": {

                "id":
                user.id,

                "name":
                user.name,

                "email":
                user.email
            }
        }

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# CREATE CONVERSATION

@app.post("/conversation")
async def create_conversation(
    data: dict
):

    db: Session = SessionLocal()

    try:

        conversation = Conversation(

            title=data.get(
                "title",
                "New Chat"
            ),

            user_id=data.get(
                "user_id"
            )
        )

        db.add(conversation)

        db.commit()

        db.refresh(conversation)

        # RESET MEMORY

        conversation_contexts[
            conversation.id
        ] = ""

        return {

            "id":
            conversation.id,

            "title":
            conversation.title
        }

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# GET CONVERSATIONS

@app.get("/conversations/{user_id}")
async def get_conversations(
    user_id: int
):

    db: Session = SessionLocal()

    try:

        conversations = db.query(
            Conversation
        ).filter(
            Conversation.user_id ==
            user_id
        ).all()

        return conversations

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# DELETE CONVERSATION

@app.delete(
    "/conversation/{conversation_id}"
)
async def delete_conversation(
    conversation_id: int
):

    db: Session = SessionLocal()

    try:

        db.query(
            Message
        ).filter(
            Message.conversation_id ==
            conversation_id
        ).delete()

        db.query(
            Conversation
        ).filter(
            Conversation.id ==
            conversation_id
        ).delete()

        db.commit()

        # REMOVE MEMORY

        if (
            conversation_id
            in
            conversation_contexts
        ):

            del conversation_contexts[
                conversation_id
            ]

        return {
            "message":
            "Conversation deleted"
        }

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# SAVE MESSAGE

@app.post("/message")
async def save_message(
    data: dict
):

    db: Session = SessionLocal()

    try:

        message = Message(

            conversation_id=data.get(
                "conversation_id"
            ),

            role=data.get("role"),

            content=data.get(
                "content"
            )
        )

        db.add(message)

        db.commit()

        db.refresh(message)

        return {
            "message":
            "Saved"
        }

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# GET MESSAGES

@app.get("/messages/{conversation_id}")
async def get_messages(
    conversation_id: int
):

    db: Session = SessionLocal()

    try:

        messages = db.query(
            Message
        ).filter(
            Message.conversation_id ==
            conversation_id
        ).all()

        return messages

    except Exception as e:

        return {
            "error": str(e)
        }

    finally:

        db.close()

# PDF UPLOAD

@app.post("/upload-pdf")
async def upload_pdf(

    conversation_id: int = Form(...),

    file: UploadFile = File(...)
):

    try:

        file_path = (
            f"uploads/{uuid.uuid4()}_{file.filename}"
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        # READ PDF

        reader = PdfReader(
            file_path
        )

        extracted_text = ""

        for page in reader.pages:

            text = page.extract_text()

            if text:

                extracted_text += (
                    text + "\n"
                )

        # OCR FALLBACK

        if not extracted_text.strip():

            extracted_text = (
                extract_text_from_scanned_pdf(
                    file_path
                )
            )

        # STORE CHAT MEMORY

        conversation_contexts[
            conversation_id
        ] = extracted_text

        # CHUNK TEXT

        chunks = chunk_text(
            extracted_text
        )

        # STORE EMBEDDINGS

        for chunk in chunks:

            embedding = create_embedding(
                chunk
            )

            collection.add(

                ids=[
                    str(uuid.uuid4())
                ],

                embeddings=[
                    embedding
                ],

                documents=[
                    chunk
                ],

                metadatas=[
                    {
                        "conversation_id":
                        conversation_id
                    }
                ]
            )

        return {

            "message":
            "PDF uploaded successfully",

            "chunks":
            len(chunks)
        }

    except Exception as e:

        return {
            "error": str(e)
        }

# CHAT

@app.post("/chat")
async def chat(
    data: dict
):

    try:

        user_message = data.get(
            "message"
        )

        conversation_id = data.get(
            "conversation_id"
        )

        if not user_message:

            return {
                "error":
                "Message required"
            }

        # GET CONVERSATION CONTEXT

        context = (
            conversation_contexts.get(
                conversation_id,
                ""
            )
        )

        # RAG VECTOR SEARCH

        retrieved_context = ""

        if context:

            try:

                query_embedding = (
                    create_embedding(
                        user_message
                    )
                )

                results = collection.query(

                    query_embeddings=[
                        query_embedding
                    ],

                    n_results=5
                )

                retrieved_docs = (
                    results.get(
                        "documents",
                        [[]]
                    )[0]
                )

                if retrieved_docs:

                    retrieved_context = (
                        "\n\n".join(
                            retrieved_docs
                        )
                    )

            except Exception as rag_error:

                print(
                    "RAG Error:",
                    rag_error
                )

        # SYSTEM PROMPT

        system_prompt = f"""
You are SupportAI, a professional AI assistant.

Your responsibilities:
- Help users professionally
- Answer clearly and accurately
- Use uploaded PDF/document context ONLY if relevant
- If context is unrelated, ignore it
- Format answers beautifully
- Keep responses concise but intelligent

DOCUMENT CONTEXT:
{retrieved_context}
"""

        # STREAM GENERATOR

        def generate():

            try:

                stream = ollama.chat(

                    model="llama3",

                    messages=[

                        {
                            "role": "system",

                            "content":
                            system_prompt
                        },

                        {
                            "role": "user",

                            "content":
                            user_message
                        }
                    ],

                    stream=True
                )

                for chunk in stream:

                    if (
                        "message" in chunk
                        and
                        "content"
                        in chunk["message"]
                    ):

                        content = chunk[
                            "message"
                        ]["content"]

                        yield content

            except Exception as stream_error:

                print(
                    "Streaming Error:",
                    stream_error
                )

                yield (
                    "❌ AI response failed."
                )

        return StreamingResponse(

            generate(),

            media_type=
            "text/plain"
        )

    except Exception as e:

        print(
            "Chat Route Error:",
            e
        )

        return {
            "error": str(e)
        }

# SEARCH

@app.post("/search")
async def semantic_search(
    data: dict
):

    try:

        query = data.get(
            "query"
        )

        embedding = create_embedding(
            query
        )

        results = collection.query(

            query_embeddings=[
                embedding
            ],

            n_results=5
        )

        return {
            "results":
            results["documents"]
        }

    except Exception as e:

        return {
            "error": str(e)
        }