# Nexus: Pure Local Voice AI & RAG System

Nexus is a 100% offline, privacy-first Voice AI assistant designed to scrape, vectorize, and answer questions based on a specific college administration portal. It features a full duplex local voice pipeline (Speech-to-Text and Text-to-Speech), wake-word detection, conversation memory, and a custom RAG (Retrieval-Augmented Generation) engine.

---

## 🌟 Key Features

* **100% Local Processing:** No data is sent to the internet. Uses local LLMs, local STT, and local TTS.
* **Automated Web Scraping (Playwright):** Automatically logs into the IQARENA portal, handles infinite scrolling to extract text (Departments, Faculty & Staff, Students), and downloads Test-Wise PDF reports.
* **Local RAG Engine (ChromaDB):** Vectorizes all scraped text and PDFs using `SentenceTransformers` to provide context-aware answers to the LLM.
* **Wake-Word Detection:** Idles in the background using minimal CPU until the user says *"Hey Nexus"*.
* **Custom Audio Greetings & Beeps:** Plays a notification beep and a custom greeting (Kratos voice) upon waking up.
* **Interruptible Speech:** Uses duplex audio streaming. If the AI is speaking and the user loudly says *"Stop"*, it instantly halts playback and listens for a new query.
* **Conversation Memory:** Retains the last 4 conversational turns for contextual awareness.

---

## 🏗️ System Architecture

1. **LLM Engine:** `llama-server.exe` running a quantized **Llama-3.2-3B-Instruct** GGUF model.
2. **Speech-to-Text (STT):** `Faster-Whisper` running locally for blazing-fast transcription.
3. **Text-to-Speech (TTS):** Pre-compiled Windows binary of **Piper TTS** using the `en_US-lessac-medium` ONNX model.
4. **Microphone I/O:** `sounddevice` and `soundfile` for non-blocking, multi-threaded audio recording and playback.
5. **Database:** `ChromaDB` for local vector storage.

---

## 📁 File Structure

* `run_local.ps1` - The main entry point. Starts the Llama server in the background and launches the Voice Bot.
* `nexus_voice.py` - The core Voice AI loop. Handles audio recording, VAD (silence detection), STT, LLM querying, and TTS playback.
* `scraper.py` - The Playwright web scraper. Extracts data from the portal and embeds it into ChromaDB.
* `rag.py` - Contains the ChromaDB initialization and context-retrieval logic.
* `config.py` - Stores credentials, URLs, and server configurations.
* `convert.py` - *(Utility)* Quick script used to convert MP3 files to WAV via FFmpeg.
* `agent.py` & `local_stt.py` - *(Legacy)* Original implementations using the LiveKit WebRTC framework before pivoting to a pure local hardware implementation.

---

## 🚀 Installation & Setup

### Prerequisites
* Windows OS with PowerShell
* Python 3.10+
* A downloaded Llama-3.2 GGUF model (Update the path in `run_local.ps1`)

### Dependencies
Install the required Python packages:
```bash
pip install faster-whisper openai sounddevice soundfile numpy schedule playwright langchain langchain-community langchain-text-splitters chromadb sentence-transformers
```
Install the Playwright browsers:
```bash
playwright install chromium
```

*(Note: The Piper TTS binary and voice models do not need to be manually installed. `nexus_voice.py` will automatically download them from GitHub and HuggingFace upon the first run.)*

---

## 💻 Usage

### 1. Update the Database
Whenever you want to pull the latest data from the college portal (new students, faculty, or test PDFs), run the scraper manually. It uses an `upsert` mechanism to prevent duplicate database entries.
```powershell
python scraper.py
```

### 2. Start the Voice AI
To start talking to Nexus, run the master PowerShell script. It will boot up the Llama server, initialize the microphone, and wait for your wake word.
```powershell
.\run_local.ps1
```

### 3. Voice Commands
* **"Hey Nexus"**: Wakes the bot up.
* **"Stop" / "Quiet"**: Say this while the bot is speaking to instantly interrupt it.
* **"Exit" / "Sleep"**: Puts the bot back into sleep mode (waiting for the wake word).

---

## 🛠️ Notes for Future Developers

* **Voice Cloning:** Piper TTS does *not* support dynamic zero-shot voice cloning from a `.wav` file. It relies on pre-trained `.onnx` models. The Kratos `.wav` file is mapped to play explicitly as a hardcoded greeting. If dynamic voice cloning is required in the future, Piper must be replaced with a heavier engine like `XTTS_v2` or `F5-TTS` (requires a dedicated GPU).
* **Interrupt Logic:** The interrupt feature (`listen_for_stop()` in `nexus_voice.py`) works by recording 1.5-second chunks of audio while TTS is playing. It uses an RMS volume threshold (`0.04`) to ignore the echo of its own speakers. If you switch to headphones, you can lower this threshold for higher sensitivity.
* **LiveKit:** If you ever wish to expose this AI over the internet to a web-browser or mobile app, you can revert to the WebRTC architecture using the included `agent.py` script alongside a `livekit-server`.
