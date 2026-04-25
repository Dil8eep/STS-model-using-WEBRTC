# WebRTC Speech AI with Django

A real-time speech demo built with Django, WebRTC, `aiortc`, and OpenAI. The browser captures microphone audio, sends it to a Django backend over WebRTC, the server transcribes the speech, generates a text response, converts that response to audio, and streams the audio reply back to the browser.

This project is a lightweight starting point for voice assistant experiments, speech-to-speech prototypes, and browser-based AI conversation workflows.

## What This Project Does

- Captures microphone audio in the browser
- Establishes a WebRTC connection between the browser and the Django backend
- Receives audio on the server using `aiortc`
- Converts captured PCM audio into a WAV file
- Sends the audio to OpenAI for transcription
- Sends the transcript to an OpenAI chat model for a response
- Uses Google Text-to-Speech (`gTTS`) to generate an MP3 reply
- Streams the generated audio back to the browser as a WebRTC audio track

## Tech Stack

- Python
- Django
- WebRTC
- `aiortc`
- OpenAI API
- `gTTS`
- NumPy
- PyAV / `av`
- SQLite

## Project Structure

```text
.
|-- manage.py
|-- requirements.txt
|-- templates/
|   `-- index.html
|-- static/
|   `-- webrtc.js
|-- speechapp/
|   |-- urls.py
|   |-- views.py
|   `-- webrtc_server.py
`-- speechproject/
    |-- asgi.py
    |-- settings.py
    `-- urls.py
```

## How It Works

### 1. Browser starts the WebRTC session

The frontend in `static/webrtc.js`:

- requests microphone permission
- creates an `RTCPeerConnection`
- adds the local microphone audio track
- creates a WebRTC offer
- sends the offer to the Django endpoint at `/offer/`

### 2. Django receives the offer

The endpoint in `speechapp/views.py`:

- accepts the incoming offer as JSON
- passes the offer data to the WebRTC handler
- returns the generated WebRTC answer to the browser

### 3. The server receives audio

The WebRTC server logic in `speechapp/webrtc_server.py`:

- creates a peer connection with a public Google STUN server
- accepts the browser's remote description
- listens for incoming audio tracks
- collects a chunk of incoming audio frames
- converts them into mono PCM audio bytes

### 4. Audio is transcribed and answered

The backend then:

- wraps the PCM stream in WAV format
- sends the WAV file to OpenAI transcription
- extracts the recognized text
- sends the recognized text to an OpenAI chat completion
- receives a concise assistant reply

### 5. The reply is turned into speech

The server:

- generates speech from the text reply using `gTTS`
- decodes and resamples the MP3 output
- pushes audio frames into an outbound WebRTC audio track
- sends the generated audio stream back to the browser

## Features

- Browser-to-server audio streaming with WebRTC
- Async Django view for WebRTC signaling
- Server-side speech transcription
- AI-generated text response
- Speech playback streamed back to the browser
- Simple single-page frontend for quick testing

## Requirements

Before running the project, make sure you have:

- Python 3.10+ installed
- `pip` available
- an OpenAI API key
- internet access for OpenAI API calls and Google TTS

## Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

Add your environment variables in a root-level `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TRANSCRIBE_MODEL=gpt-4o-transcribe
OPENAI_CHAT_MODEL=gpt-4o-mini
```

## Running the Project

Start the Django development server:

```bash
python manage.py runserver
```

Then open:

```text
http://127.0.0.1:8000/
```

Click **Start Talking**, allow microphone access, and speak for a few seconds.

## Main Endpoints

### `GET /`

Serves the main browser UI from `templates/index.html`.

### `POST /offer/`

Accepts a WebRTC offer and returns a WebRTC answer.

Example request body:

```json
{
  "sdp": "v=0...",
  "type": "offer"
}
```

Example response body:

```json
{
  "sdp": "v=0...",
  "type": "answer"
}
```

## Environment Variables

The project loads environment variables from `.env` using `python-dotenv`.

Supported variables:

- `OPENAI_API_KEY`: required for OpenAI API access
- `OPENAI_TRANSCRIBE_MODEL`: optional, defaults to `gpt-4o-transcribe`
- `OPENAI_CHAT_MODEL`: optional, defaults to `gpt-4o-mini`

## Notes About the Current Implementation

- The Django `SECRET_KEY` is hardcoded in settings and should be moved to an environment variable before production use.
- `DEBUG` is enabled.
- `ALLOWED_HOSTS` is empty and should be configured for deployment.
- SQLite is used as the default database.
- Generated audio files are stored in the local `media/` directory.
- The current audio collection logic captures a limited chunk of audio before processing.
- The UI is intentionally minimal and built for testing rather than polished product use.
- CSRF is disabled for the `/offer/` endpoint to simplify local signaling.

## Limitations

- This is a development/demo project, not a production-ready voice platform.
- It does not currently include authentication or user session management for the speech flow.
- It does not include advanced retry logic, queue management, or cleanup for long-running connections.
- It depends on external services for both transcription/chat and text-to-speech.
- There are no automated tests in the repository yet.
- The speech flow is near-real-time but not fully streaming transcription and streaming generation end-to-end.

## Suggested Improvements

- Move `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS` into environment variables
- Add production-grade ASGI deployment with Daphne, Uvicorn, or Hypercorn
- Add TURN server support for more reliable NAT traversal
- Replace `gTTS` with a lower-latency streaming TTS option
- Add frontend transcript and response text display
- Add connection cleanup and better lifecycle handling
- Add tests for signaling and audio-processing logic
- Add Docker support for easier local setup

## Dependencies

Current Python dependencies from `requirements.txt`:

- `django`
- `python-dotenv`
- `aiortc`
- `av`
- `numpy`
- `openai`
- `gtts`

## Demo Flow Summary

1. User clicks the button in the browser.
2. Browser captures microphone audio.
3. Browser sends a WebRTC offer to Django.
4. Django accepts the WebRTC connection.
5. Server collects incoming audio frames.
6. Audio is transcribed with OpenAI.
7. Transcript is sent to an OpenAI chat model.
8. AI response text is converted to speech.
9. Speech audio is streamed back to the browser.

## Security Reminder

Do not commit your `.env` file or API keys. This repository already includes `.gitignore` rules to keep local secrets out of source control.

## License

Add a license file if you plan to publish or share this project publicly on GitHub.
