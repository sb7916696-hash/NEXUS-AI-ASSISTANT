import os
import wave
import time
import urllib.request
import zipfile
import subprocess
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from openai import OpenAI
import config
from rag import retrieve_context
import threading

# ==========================================
# 1. SETUP PIPER TTS LOCALLY
# ==========================================
PIPER_DIR = "piper_tts"
PIPER_EXE = os.path.join(PIPER_DIR, "piper", "piper.exe")
VOICE_MODEL = os.path.join(PIPER_DIR, "en_US-lessac-medium.onnx")
VOICE_JSON = os.path.join(PIPER_DIR, "en_US-lessac-medium.onnx.json")

def setup_piper():
    if not os.path.exists(PIPER_DIR):
        os.makedirs(PIPER_DIR)
        
    if not os.path.exists(PIPER_EXE):
        print("[Setup] Downloading Piper TTS binary for Windows...")
        zip_path = os.path.join(PIPER_DIR, "piper.zip")
        urllib.request.urlretrieve("https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip", zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(PIPER_DIR)
        os.remove(zip_path)
        
    if not os.path.exists(VOICE_MODEL):
        print("[Setup] Downloading Piper Voice Model...")
        urllib.request.urlretrieve("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx", VOICE_MODEL)
        urllib.request.urlretrieve("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json", VOICE_JSON)
    print("[Setup] Piper TTS ready.")

# ==========================================
# 2. AUDIO RECORDING & PLAYBACK 
# ==========================================
is_playing = False

play_event = threading.Event()

def play_audio(filename, delete_after=False):
    global is_playing
    try:
        data, fs = sf.read(filename, dtype="float32")
        is_playing = True
        play_event.set()
        sd.play(data, fs)
        sd.wait()
    except Exception as e:
        print(f"[Audio Error] {e}")
    finally:
        is_playing = False
        if delete_after and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass

import re
import uuid

def clean_text_for_speech(text):
    # Remove markdown formatting (**, *, #, `) and special unicode
    text = re.sub(r'[*#_`~]', '', text)
    # Replace newlines with spaces for smoother TTS
    text = text.replace('\n', ' ')
    # Encode/decode to remove emojis which crash Piper on stdin
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.strip()

def speak(text, whisper_model=None):
    global is_playing
    play_event.clear()
    cleaned_text = clean_text_for_speech(text)
    if not cleaned_text: return
    print(f"[Nexus] Speaking: {cleaned_text}")
    wav_file = f"temp_output_{uuid.uuid4().hex[:8]}.wav"
    try:
        result = subprocess.run([PIPER_EXE, "-m", VOICE_MODEL, "-f", wav_file], input=cleaned_text.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            print(f"[Voice System Error] Piper failed:\\n{result.stderr.decode('utf-8', errors='ignore')}")
            return
    except Exception as e:
        print(f"[Voice System Error] Piper crash: {e}")
        return
    threading.Thread(target=play_audio, args=(wav_file, True), daemon=True).start()
    
    # We no longer listen for interrupts because it causes an echo-loop 
    # where the mic hears the TTS, starts transcribing, maxes out CPU, and cracks the audio.
    while not play_event.is_set(): time.sleep(0.05)
    while is_playing: time.sleep(0.1)


def record_until_silence(samplerate=16000, threshold=0.015, silence_duration=1.5, max_duration=10.0):
    audio_data = []
    silent_chunks = 0
    chunk_size = int(samplerate * 0.1) # 100ms chunks
    max_chunks = int(max_duration / 0.1)
    
    with sd.InputStream(samplerate=samplerate, channels=1, dtype='float32') as stream:
        started = False
        while True:
            chunk, _ = stream.read(chunk_size)
            volume = np.max(np.abs(chunk))
            
            if not started:
                if volume > threshold:
                    # Let the user know the mic triggered!
                    print("\n[Mic] Audio detected, recording...", end="", flush=True)
                    started = True
                    audio_data.append(chunk)
            else:
                audio_data.append(chunk)
                if volume < threshold:
                    silent_chunks += 1
                else:
                    silent_chunks = 0
                
                # Print a dot every 1 second of recording so the user sees it's alive
                if len(audio_data) % 10 == 0:
                    print(".", end="", flush=True)
                
                # Stop if silence duration is reached, OR if we hit the max recording limit
                if silent_chunks > (silence_duration / 0.1):
                    print(" (Silence detected)")
                    break
                if len(audio_data) >= max_chunks:
                    print(" (Max duration reached)")
                    break

    recording = np.concatenate(audio_data)
    recording = (recording * 32767).astype(np.int16)
    wav_file = "temp_input.wav"
    with wave.open(wav_file, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(recording.tobytes())
        
    return wav_file

# ==========================================
# 3. MEMORY MANAGEMENT
# ==========================================
chat_history = []
MAX_HISTORY = 4 # Keep last 4 turns to save memory

def add_to_memory(role, content):
    chat_history.append({"role": role, "content": content})
    if len(chat_history) > MAX_HISTORY * 2:
        del chat_history[0:2] # Remove oldest user/assistant pair

def get_memory():
    return chat_history

# ==========================================
# 4. MAIN LOOP
# ==========================================
def main():
    setup_piper()
    
    print("\n[Setup] Loading Faster-Whisper...")
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    client = OpenAI(base_url=config.LLM_SERVER_URL, api_key="local")
    
    system_prompt = (
        "You are Nexus, a polite, helpful AI assistant for Nadar Saraswathi College of Engineering and Technology (NSCET). "
        "Keep your answers brief (1-3 sentences). "
        "CRITICAL: You must ONLY use the provided context to answer. Do NOT add any extra information, do NOT hallucinate, "
        "and do NOT invent any details that are not explicitly stated in the context. If the context doesn't contain the answer, "
        "strictly say you don't know."
    )

    BEEP_FILE = "universfield-new-notification-07-210334.wav"

    print("\n=========================================")
    print(" NEXUS PURE LOCAL VOICE BOT STARTED")
    print(" Waiting for wake word: 'Hey Nexus'")
    print("=========================================\n")

    mode = "WAKE_WORD"

    while True:
        try:
            if mode == "WAKE_WORD":
                audio_file = record_until_silence()
                print("\n[Nexus] Processing audio...") # Let user know it heard something
                segments, _ = whisper_model.transcribe(audio_file, beam_size=5, initial_prompt="Hey Nexus. Nadar Saraswathi College of Engineering and Technology (NSCET).")
                transcript = " ".join([s.text for s in segments]).strip().lower()
                
                # Debug print so you can see what your mic is actually hearing
                if transcript:
                    print(f"[Debug] I heard: '{transcript}'")
                
                # Extreme lenient matching for phonetic mishearings
                # Whisper is hearing "Hey Nexus" as "here in axis", "a and xs", etc.
                wake_variants = ["nexus", "axis", "xs", "next us", "lexus", "excess", "nexis", "nix"]
                
                # Check if any variant is in the transcript as a standalone word or substring
                woke_up = any(variant in transcript.lower() for variant in wake_variants)
                
                if woke_up:
                    print("\n*** [WAKE WORD DETECTED] ***")
                    
                    # 1. Play Notification Beep
                    if os.path.exists(BEEP_FILE):
                        play_audio(BEEP_FILE)
                    
                    speak("Hi, I am Nexus. How can I help you?")
                    
                    # 3. Switch to listening for a query
                    mode = "LISTENING"
                else:
                    if transcript:
                        print("[Nexus] (Waiting for wake word...)")
            
            elif mode == "LISTENING":
                print("\n[Nexus] Listening for query... (Say 'stop' during my answer to interrupt, or wait to ask)")
                audio_file = record_until_silence()
                segments, _ = whisper_model.transcribe(audio_file, beam_size=5, initial_prompt="Hey Nexus. Nadar Saraswathi College of Engineering and Technology (NSCET).")
                transcript = " ".join([s.text for s in segments]).strip()
                
                if not transcript or len(transcript) < 3:
                    mode = "WAKE_WORD" # Go back to sleep if nothing heard
                    continue
                    
                print(f"\n[User]: {transcript}")
                
                if "stop" in transcript.lower() or "exit" in transcript.lower() or "sleep" in transcript.lower():
                    speak("Goodbye!")
                    mode = "WAKE_WORD"
                    continue

                # Add User to memory
                add_to_memory("user", transcript)

                # Retrieve Context (RAG)
                context = retrieve_context(transcript)
                if context:
                    print("\n--- [RAG Context Retrieved] ---")
                    print(context[:300] + "...\n-------------------------------")
                
                # Build Prompt
                messages = [{"role": "system", "content": system_prompt}]
                if context:
                    messages.append({"role": "system", "content": f"Context:\n{context}"})
                
                # Append Memory
                messages.extend(get_memory())
                
                # Think (LLM)
                print("[Nexus] Thinking...")
                response = client.chat.completions.create(
                    model="llama",
                    messages=messages,
                    temperature=0.3
                )
                reply = response.choices[0].message.content.strip()
                
                # Add Assistant to memory
                add_to_memory("assistant", reply)
                
                # Speak (with interrupt enabled!)
                speak(reply, whisper_model=whisper_model)
                
                # Loop back to listening for a follow-up query
                mode = "LISTENING"
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Main Loop Error]: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
