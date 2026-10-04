import os
import time
import json
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from supabase import Client, create_client

# ============================================================
# CONFIGURATION
# ============================================================

# Charger les variables d'environnement
load_dotenv()

SUPABASE_URL = "https://eihloelsodssvmczdqnr.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_lxyaxo_8PZSY89cGcfNOog_o15SZe8P"

# Configuration des backends
BACKENDS = {
    "local": {
        "base_url": "http://localhost:1337/v1",
        "model": "Jan-code-4b-Q4_K_M",
        "api_key": None,
        "type": "jan"
    },
    "home": {
        "base_url": f"http://{os.getenv('OLLAMA_HOST_IP', '192.168.1.15')}:{os.getenv('OLLAMA_PORT', '11434')}/v1",
        "model": os.getenv("OLLAMA_MODEL", "qwen2.5-coder:32b"), #gemma4:26b
        #"model": "ollama-home"
        "api_key": None,
        "type": "ollama"
    },
    "cloud": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "ministral-8b-latest",
        "api_key": os.getenv("MISTRAL_API_KEY"),
        "type": "mistral"
    }
}

# Backend par défaut (à changer manuellement pour le POC)
CURRENT_BACKEND = "cloud"  # ou "home" ou "cloud" ou "local" 

ORCHESTRATOR_HOST = "127.0.0.1"
ORCHESTRATOR_PORT = 8000

# ============================================================
# CLIENTS
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
)

def get_llm_client():
    """Retourne le client LLM en fonction du backend sélectionné."""
    backend_config = BACKENDS[CURRENT_BACKEND]
    return ChatOpenAI(
        base_url=backend_config["base_url"],
        api_key=backend_config["api_key"] or "not-needed",
        model=backend_config["model"],
        temperature=0.2,
        streaming=True
    )

# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Local LLM Orchestrator"
)

# ============================================================
# OPENAI-COMPATIBLE /v1/models
# ============================================================

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "custom_orchestrator",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-orchestrator"
            }
        ]
    }

# ============================================================
# OPENAI-COMPATIBLE /v1/chat/completions
# ============================================================

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Récupérer les données de la requête
    request_data = await request.json()
    user_prompt = request_data.get("messages", [{}])[-1].get("content", "")
    stream = request_data.get("stream", False)

    # Initialiser le client LLM
    llm = get_llm_client()
    prompt_template = ChatPromptTemplate.from_messages([
        ("human", "{input}")
    ])
    chain = prompt_template | llm | StrOutputParser()

    # ========================================================
    # LOGGING DANS SUPABASE (via Requests pour éviter les conflits RLS du SDK)
    # ========================================================
    def log_to_supabase(response_content: str = None):
        """Log la requête et la réponse dans Supabase via l'API REST directe."""
        payload = {
            "source_app": "Local LLM Orchestrator",
            "prompt": str(user_prompt),
            "response": str(response_content) if response_content else "STREAMED",
            "model_used": "Jan-local_TEST", # On garde la valeur qui fonctionne
            "backend_used": CURRENT_BACKEND,
            "debug_info": json.dumps({
                "backend_type": BACKENDS[CURRENT_BACKEND]["type"],
                "backend_url": BACKENDS[CURRENT_BACKEND]["base_url"]
            })
        }
        
        try:
            response = requests.post(
                f"{SUPABASE_URL.rstrip('/')}/rest/v1/agent_logs",
                headers={
                    "apikey": SUPABASE_PUBLISHABLE_KEY.strip(),
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=payload,
                timeout=15,
            )
            if response.status_code >= 400:
                print(f"Supabase ERROR {response.status_code}: {response.text}")
            else:
                print("Supabase LOG SUCCESS")
        except Exception as e:
            print("Supabase REQUEST ERROR:", repr(e))

    # ========================================================
    # STREAMING
    # ========================================================
    async def event_generator():
        full_response = ""
        try:
            async for chunk in chain.astream({"input": user_prompt}):
                full_response += chunk
                # OpenAI-compatible chunk format
                chunk_data = {
                    "choices": [
                        {
                            "delta": {"content": chunk},
                            "index": 0,
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
            # Signal completion to the client (CRITICAL for "Premature close" fix)
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"Streaming error: {e}")
            full_response = f"Error during streaming: {str(e)}"
        finally:
            # Log the response (even if it was an error)
            log_to_supabase(full_response)

    # ========================================================
    # NON-STREAMING
    # ========================================================
    if not stream:
        full_response = await chain.ainvoke({"input": user_prompt})
        log_to_supabase(full_response)
        return JSONResponse({
            "id": f"chatcmpl-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": BACKENDS[CURRENT_BACKEND]["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_response
                    },
                    "finish_reason": "stop"
                }
            ]
        })

    # ========================================================
    # STREAMING
    # ========================================================
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

# ============================================================
# LANCEMENT DIRECT
# ============================================================

if __name__ == "__main__":
    import uvicorn

    print()
    print("======================================")
    print(" ORCHESTRATOR STARTING")
    print("======================================")
    print("FastAPI :", f"http://{ORCHESTRATOR_HOST}:{ORCHESTRATOR_PORT}")
    print("Current Backend :", CURRENT_BACKEND)
    print("Backend URL :", BACKENDS[CURRENT_BACKEND]["base_url"])
    print("Model :", BACKENDS[CURRENT_BACKEND]["model"])
    print("======================================")
    print()

    uvicorn.run(
        app,
        host=ORCHESTRATOR_HOST,
        port=ORCHESTRATOR_PORT
    )