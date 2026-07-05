import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from gotrue.errors import AuthApiError
from langchain_huggingface import HuggingFaceEndpoint
from composio import Composio
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from contextlib import asynccontextmanager
from datetime import datetime
from langchain_core.messages import SystemMessage
import base64

from src.speech_to_text import speech_2_text
from src.text_to_speech import text_2_speech
from src.graph import app_graph
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

DB_URI = os.getenv("DATABASE_URL")
compiled_graph = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global compiled_graph

    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:

        await checkpointer.setup()

        compiled_graph = app_graph.compile(
            checkpointer=checkpointer
        )

        yield

app = FastAPI(lifespan=lifespan)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY")



supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
composio = Composio(api_key=COMPOSIO_API_KEY)

# 3. Define the Pydantic schemas
class UserCredentials(BaseModel):
    email: str
    password: str

class ConnectRequest(BaseModel):
    user_id: str  

@app.post("/signup")
async def sign_up(user: UserCredentials):
    try:
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password
        })
        
        if auth_response.user and not auth_response.user.identities:
            raise HTTPException(status_code=400, detail="Already registered")
            
        user_id = auth_response.user.id
        
        supabase.table("user_information").insert({
            "id": user_id, 
            "email": user.email
        }).execute()
            
        return {"message": "User registered successfully", "user_id": user_id}
        
    except AuthApiError as e:
        if "already registered" in e.message.lower() or "already exists" in e.message.lower():
            raise HTTPException(status_code=400, detail="Already registered")
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/login")
async def login(user: UserCredentials):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        return {
            "message": "Login successful", 
            "user_id": response.user.id
        }
    except AuthApiError as e:
        message = e.message.lower()

        if "email not confirmed" in message:
            raise HTTPException(
                status_code=401,
                detail="Please verify your email before logging in."
            )

        if "invalid login credentials" in message:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password."
            )

        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/connect/services")
async def connect_services(request: ConnectRequest):
    try:
        session = composio.create(user_id=request.user_id)

        gmail_auth = session.authorize("gmail")

        calendar_auth = session.authorize("googlecalendar")

        drive_auth = session.authorize("googledrive")

        return {
            "message": "Connection links generated successfully",
            "gmail_url": gmail_auth.redirect_url,
            "calendar_url": calendar_auth.redirect_url,
            "drive_url" : drive_auth.redirect_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed : {str(e)}")
    

class ChatRequest(BaseModel):
    user_id: str
    thread_id: str 
    message : str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:    
        audio_bytes = base64.b64decode(request.message)
        text = await speech_2_text(audio_bytes)

        config = {"configurable": {"thread_id": request.thread_id}}
        input_state = {
            "messages": [HumanMessage(content=text)],
            "user_id": request.user_id
        }
        
        # Use the globally compiled graph
        response = await compiled_graph.ainvoke(input_state, config=config)

        result = (
        supabase.table("chat_threads")
        .select("title")
        .eq("thread_id", request.thread_id)
        .single()
        .execute()
        )

        if result.data and result.data['title'] == "Empty Chat":
            llm = ChatOpenAI(model="openai/gpt-4o-mini",
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=0.5)
            

            res = await llm.ainvoke(
                [
                    SystemMessage(
                        content="""
        Generate a short conversation title.

        Rules:
        - Maximum 3 words
        - No quotation marks
        - Capitalize normally
        - Return only the title.
        """
                    ),
                    HumanMessage(content=text),
                ]
            )

            new_title =  res.content.strip()

            supabase.table("chat_threads").update(
            {
                "title": new_title
            }
            ).eq(
                "thread_id",
                request.thread_id
            ).execute()

        content = response["messages"][-1].content

        if isinstance(content, str):
            answer = content

        elif isinstance(content, list):
            answer = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )

        else:
            answer = str(content)

        if "<LINK>" in answer :
            audio_input = answer.split("<LINK>")[0]
            display_text = audio_input + " " + answer.split("<LINK>")[1]
        
        else :
            audio_input = display_text = answer
        
        audio_stream = await text_2_speech(audio_input)
        print("=" * 80)
        print("LLM RESPONSE:")
        print(repr(response["messages"][-1].content))
        print("=" * 80)
        raw_audio_bytes = audio_stream.getvalue()
        
        base64_audio = base64.b64encode(raw_audio_bytes).decode("utf-8")
        audio_data_url = f"data:audio/mpeg;base64,{base64_audio}"

        return {"user_text" : text,
                "reply": display_text,
                "audio_reply" : audio_data_url}
        
    except Exception as e:
        print(f"Error in /chat: {e}") # Log securely
        raise HTTPException(status_code=500, detail="error")
    

class ThreadCreateRequest(BaseModel):
    user_id: str
    thread_id: str
    title: str = "New Conversation"

@app.post("/threads", status_code=201)
async def create_new_thread(thread: ThreadCreateRequest):
    response = supabase.table("chat_threads").insert({
        "thread_id": thread.thread_id,
        "user_id": thread.user_id,
        "title": thread.title,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    
    return {"message": "Thread tracked successfully", "data": response.data}

@app.get("/threads/{user_id}")
async def get_user_threads(user_id: str):
    response = supabase.table("chat_threads").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return {"threads": response.data}

@app.get("/chat/history/{thread_id}")
async def get_chat_history(thread_id: str):

    config = {"configurable": {"thread_id": thread_id}}

    state_snapshot = await compiled_graph.aget_state(config=config)
    
    if not state_snapshot or not hasattr(state_snapshot, 'values') or "messages" not in state_snapshot.values:
        return {"messages": []}

    formatted_messages = []
    for msg in state_snapshot.values["messages"]:
        if msg.type == "tool":
            continue
        role = "user" if msg.type == "human" else "assistant"
        formatted_messages.append({
            "role": role,
            "content": msg.content
        })
        
    return {"messages": formatted_messages}

@app.get("/user/{user_id}/connection-status")
def get_connection_status(user_id: str):
    user_data = supabase.table("user_information").select("services_connected").eq("id", user_id).single().execute()
    
    is_connected = user_data.data.get("services_connected", False)
    return {"is_connected": is_connected}

@app.post("/user/{user_id}/confirm-connection")
def confirm_connection(user_id: str):
    try:
        response = supabase.table("user_information")\
            .update({"services_connected": True})\
            .eq("id", user_id)\
            .execute()
        
        return {"success": True, "message": "Connection verified and updated."}
    except Exception as e:
        print(f"Error updating connection: {e}")
        return {"success": False, "detail": str(e)}