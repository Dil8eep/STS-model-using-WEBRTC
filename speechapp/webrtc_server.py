import asyncio
import io
import logging
import os
import tempfile
import uuid
import wave
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCConfiguration,
    RTCIceServer,
    RTCSessionDescription,
)


MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)

pcs: set[RTCPeerConnection] = set()

AUDIO_SAMPLE_RATE = 48_000
AUDIO_CHANNELS = 1
AUDIO_FRAME_SAMPLES = 960
STUN_SERVERS = [RTCIceServer(urls=["stun:stun.l.google.com:19302"])]


async def _wait_for_ice_gathering_complete(pc: RTCPeerConnection) -> None:
    if pc.iceGatheringState == "complete":
        return

    ice_complete = asyncio.Event()

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange() -> None:
        if pc.iceGatheringState == "complete":
            ice_complete.set()

    await ice_complete.wait()


def _write_wav_bytes(raw_pcm: bytes, sample_rate: int, channels: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(raw_pcm)
    buffer.seek(0)
    return buffer.read()


def _get_openai_client():
    from openai import OpenAI

    return OpenAI()


class OutboundAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self) -> None:
        super().__init__()
        self._queue: asyncio.Queue[av.AudioFrame] = asyncio.Queue()
        self._pts = 0

    async def recv(self) -> av.AudioFrame:
        try:
            frame = await asyncio.wait_for(self._queue.get(), timeout=0.02)
        except asyncio.TimeoutError:
            silence = np.zeros((AUDIO_CHANNELS, AUDIO_FRAME_SAMPLES), dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(silence, format="s16", layout="mono")
            frame.sample_rate = AUDIO_SAMPLE_RATE

        frame.pts = self._pts
        frame.time_base = Fraction(1, AUDIO_SAMPLE_RATE)
        self._pts += frame.samples
        return frame

    async def enqueue_tts(self, text: str) -> str:
        from gtts import gTTS

        filename = MEDIA_DIR / f"response_{uuid.uuid4()}.mp3"
        gTTS(text=text).save(str(filename))

        with av.open(str(filename)) as container:
            resampler = av.audio.resampler.AudioResampler(
                format="s16",
                layout="mono",
                rate=AUDIO_SAMPLE_RATE,
            )
            for decoded_frame in container.decode(audio=0):
                for resampled_frame in resampler.resample(decoded_frame):
                    await self._queue.put(resampled_frame)

        return str(filename)


async def process_audio(raw_pcm: bytes, sample_rate: int, response_track: OutboundAudioTrack) -> dict:
    wav_bytes = _write_wav_bytes(raw_pcm, sample_rate=sample_rate, channels=AUDIO_CHANNELS)
    client = _get_openai_client()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        temp_wav.write(wav_bytes)
        temp_path = temp_wav.name

    try:
        with open(temp_path, "rb") as audio_file:
            transcript = await asyncio.to_thread(
                client.audio.transcriptions.create,
                model=os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe"),
                file=audio_file,
            )

        user_text = (getattr(transcript, "text", "") or "").strip()
        if not user_text:
            user_text = "I did not hear any speech."

        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise, friendly voice assistant.",
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
        )

        ai_text = completion.choices[0].message.content or "I am sorry, I could not generate a response."
        audio_path = await response_track.enqueue_tts(ai_text)
        return {"transcript": user_text, "response_text": ai_text, "audio_path": audio_path}
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


async def handle_offer(params: dict) -> dict:
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=STUN_SERVERS))
    pcs.add(pc)
    response_track = OutboundAudioTrack()
    logger.info("Received WebRTC offer")

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        if track.kind != "audio":
            return
        logger.info("Remote audio track received from browser")

        async def collect_audio() -> None:
            audio_chunks: list[np.ndarray] = []
            sample_rate = AUDIO_SAMPLE_RATE

            try:
                for _ in range(250):
                    frame = await track.recv()
                    sample_rate = frame.sample_rate or AUDIO_SAMPLE_RATE
                    array = frame.to_ndarray()
                    if array.ndim == 1:
                        mono = array
                    else:
                        mono = array[0]
                    audio_chunks.append(mono.astype(np.int16, copy=False))
            except Exception:
                if not audio_chunks:
                    return

            if not audio_chunks:
                return

            pcm = np.concatenate(audio_chunks).astype(np.int16, copy=False).tobytes()
            await process_audio(pcm, sample_rate, response_track)

        asyncio.create_task(collect_audio())

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        logger.info("Peer connection state changed to %s", pc.connectionState)
        if pc.connectionState in {"failed", "closed"}:
            await pc.close()
            pcs.discard(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange() -> None:
        logger.info("ICE connection state changed to %s", pc.iceConnectionState)

    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange() -> None:
        logger.info("ICE gathering state changed to %s", pc.iceGatheringState)

    await pc.setRemoteDescription(offer)
    logger.info("Remote description applied")
    pc.addTrack(response_track)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await _wait_for_ice_gathering_complete(pc)
    logger.info("Local description prepared and ICE gathering complete")

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
