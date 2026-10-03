"""Audio upload validation.

Declared content types are not trusted. The file signature is checked and must
agree with an allowed container. Duration is verified exactly for WAV and is
otherwise bounded by the byte limit and the client recorder limit.
"""

import struct
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import PayloadTooLarge, UnsupportedMedia, ValidationFailed

ALLOWED_TYPES = {
    "audio/webm": ("webm", "audio/webm"),
    "video/webm": ("webm", "audio/webm"),  # some browsers label audio only WebM as video/webm
    "audio/ogg": ("ogg", "audio/ogg"),
    "audio/wav": ("wav", "audio/wav"),
    "audio/x-wav": ("wav", "audio/wav"),
    "audio/wave": ("wav", "audio/wav"),
    "audio/mpeg": ("mp3", "audio/mpeg"),
    "audio/mp3": ("mp3", "audio/mpeg"),
    "audio/mp4": ("m4a", "audio/mp4"),
    "audio/x-m4a": ("m4a", "audio/mp4"),
}


@dataclass(frozen=True)
class AudioInfo:
    container: str
    extension: str
    content_type: str
    size_bytes: int
    duration_seconds: float | None
    very_quiet: bool = False


def _sniff(data: bytes) -> str | None:
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    if data[4:8] == b"ftyp":
        return "m4a"
    return None


def _wav_details(data: bytes) -> tuple[float | None, bool]:
    """Return (duration seconds, very_quiet) for PCM16 WAV, parsing chunks defensively."""
    try:
        pos, byte_rate, bits, data_size, data_start = 12, 0, 0, 0, 0
        while pos + 8 <= len(data):
            chunk_id, size = data[pos : pos + 4], struct.unpack("<I", data[pos + 4 : pos + 8])[0]
            if chunk_id == b"fmt ":
                _fmt, _channels, _rate, byte_rate, _align, bits = struct.unpack("<HHIIHH", data[pos + 8 : pos + 24])
            elif chunk_id == b"data":
                data_size, data_start = min(size, len(data) - pos - 8), pos + 8
                break
            pos += 8 + size + (size % 2)
        if not byte_rate or not data_size:
            return None, False
        duration = data_size / byte_rate
        quiet = False
        if bits == 16 and data_size >= 3200:
            samples = struct.unpack(f"<{data_size // 2}h", data[data_start : data_start + (data_size // 2) * 2])
            peak = max(abs(s) for s in samples[:: max(1, len(samples) // 20000)])
            quiet = peak < 300  # roughly -40 dBFS peak: almost certainly silence or a muted mic
        return duration, quiet
    except (struct.error, ValueError):
        return None, False


def validate_audio(data: bytes, declared_type: str | None, settings: Settings) -> AudioInfo:
    if len(data) > settings.max_audio_bytes:
        raise PayloadTooLarge(f"Audio must be smaller than {settings.max_audio_bytes // (1024 * 1024)} MB.")
    if len(data) < settings.min_audio_bytes:
        raise ValidationFailed("The recording is too short. Please speak for a few seconds and try again.")
    base_type = (declared_type or "").split(";")[0].strip().lower()
    if base_type not in ALLOWED_TYPES:
        raise UnsupportedMedia()
    container = _sniff(data)
    extension, content_type = ALLOWED_TYPES[base_type]
    if container is None or container != extension:
        raise UnsupportedMedia("The audio file does not match its declared format.")
    duration, quiet = (None, False)
    if container == "wav":
        duration, quiet = _wav_details(data)
        if duration is not None and duration > settings.max_audio_seconds:
            raise PayloadTooLarge(f"Recording must be shorter than {settings.max_audio_seconds} seconds.")
    return AudioInfo(container, extension, content_type, len(data), duration, quiet)
