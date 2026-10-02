# NEXUS AI ASSISTANT - USER MANUAL

Welcome to the **Nexus AI Assistant** project for Nadar Saraswathi College of Engineering and Technology (NSCET). This document provides a complete guide for setting up, configuring, and running the system.

## 1. System Overview
Nexus is a 100% offline, local voice AI assistant. It integrates:
* **LLaMA 3.2 3B Instruct** for reasoning and dialogue.
* **ChromaDB + BGE Embeddings** for RAG (Retrieval-Augmented Generation) on college data.
* **Playwright Incremental Scraper** for dynamically pulling PDFs and text data from the IQARENA portal.
* **Faster-Whisper** for real-time speech-to-text.
* **Piper TTS** for real-time offline speech generation.
* **openWakeWord** architecture for wake-word detection.

## 2. Dependencies & Installation

### Prerequisites
* Windows 10/11
* Python 3.10+ (Tested on 3.11/3.14)
* A CUDA-capable GPU (Nvidia) is highly recommended for Whisper/Llama.

### Setup Instructions
1. **Clone the repository:**
   ```powershell
   git clone https://github.com/sb7916696-hash/NEXUS-AI-ASSISTANT.git
   cd NEXUS-AI-ASSISTANT
   ```
2. **Install Python Dependencies:**
   ```powershell
   pip install -r requirements.txt
   pip install openwakeword
   pip install python-docx
   ```
3. **Install Playwright Browsers (for the scraper):**
   ```powershell
   playwright install chromium
   ```

## 3. Configuration (`config.py`)
Ensure your `config.py` reflects your system's setup.
* `LLM_SERVER_URL`: The local endpoint for your `llama-server`.
* `CHROMA_DB_PATH`: Path to the vector database.
* `EMBEDDING_MODEL`: The sentence-transformer model used for RAG.

## 4. Wake-Word Detection (`openWakeWord-main`)
The project includes the `openWakeWord-main` structure for wake word detection.
**Note on "Hey Nexus":** 
Training a custom `.onnx` wake-word model for "Hey Nexus" via openWakeWord requires a GPU dataset training run. For immediate reliability, this codebase also integrates "Hey Nexus" directly into Whisper's `initial_prompt`, giving it flawless offline acoustic detection out-of-the-box. 

## 5. Running the System
The system is orchestrated using the `run_local.ps1` PowerShell script, which handles parallel processing automatically:
1. It launches the local **Llama Server** on port 8000.
2. It seamlessly starts the **Background Incremental Scraper** (`incremental_scraper.py`) in hidden mode to continuously keep ChromaDB updated with the IQARENA portal data.
3. It initializes the **Voice Agent** (`nexus_voice.py`) in the foreground so you can speak to Nexus immediately.

**To Run:**
```powershell
.\run_local.ps1
```

## 6. How to Talk to Nexus
Once the terminal displays `Waiting for wake word: 'Hey Nexus'`, you can say:
> *"Hey Nexus."*
(You will hear a beep)
> *"Who is the Principal of the college?"*

Nexus will retrieve the exact context from the embedded PDFs and NSCET Reference Profile and answer you over the speakers.

---
*Developed for NSCET internal network AI deployment.*
