import os

# ==========================================
# NEXUS CONFIGURATION
# ==========================================

# 1. Admin Portal Scraping Configuration
# Replace these placeholders with your actual college URL and credentials
ADMIN_PORTAL_URL = os.getenv("ADMIN_PORTAL_URL", "https://iqarena.nscet.org/super-admin")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "ns9210")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123")

# 2. Local Models Configuration
# The exact path to the locally installed Llama 3.2 GGUF file
LLM_MODEL_PATH = r"C:\Users\sb791\.cache\huggingface\hub\models--bartowski--Llama-3.2-3B-Instruct-GGUF\snapshots\5ab33fa94d1d04e903623ae72c95d1696f09f9e8\Llama-3.2-3B-Instruct-Q4_K_M.gguf"
LLM_SERVER_PORT = 8000
LLM_SERVER_URL = f"http://localhost:{LLM_SERVER_PORT}/v1"

# 3. ChromaDB Configuration
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "college_data"

# 4. Embedding Model
EMBEDDING_MODEL = 'BAAI/bge-small-en-v1.5'

# 5. Faster-Whisper Configuration
WHISPER_MODEL = "base.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
