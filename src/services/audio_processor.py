import asyncio
from pathlib import Path

# 5 minutes per chunk: at the 64 kbps mp3 we encode to, that's ~2.4 MB —
# well under both Groq's 25 MB hard cap and the (looser, undocumented) body
# limits of the Deno Deploy / Cloudflare Worker proxy in front of Groq.
# Reverting to 10 min triggered consistent 500s from the proxy on long
# RuTube audio. If you bump this, also test the proxy can pass the upload
# within its per-invocation wall-clock.
CHUNK_DURATION_SECONDS = 300   # 5 minutes
OVERLAP_SECONDS = 5            # overlap for context at boundaries
GROQ_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


async def get_audio_duration(path: Path) -> float:
    """Get audio duration via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    return float(stdout.decode().strip())


async def extract_audio(input_path: Path, output_path: Path) -> Path:
    """Extract audio from video file to mp3 via ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "128k",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return output_path


async def split_audio(input_path: Path, output_dir: Path) -> list[Path]:
    """Split audio into 10-minute chunks with 5-second overlap."""
    duration = await get_audio_duration(input_path)
    chunks: list[Path] = []
    start = 0.0
    chunk_idx = 0

    while start < duration:
        chunk_path = output_dir / f"chunk_{chunk_idx:04d}.mp3"
        segment_duration = min(CHUNK_DURATION_SECONDS + OVERLAP_SECONDS, duration - start)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(segment_duration),
            "-i", str(input_path),
            "-acodec", "libmp3lame",
            "-ab", "128k",
            str(chunk_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        chunks.append(chunk_path)

        start += CHUNK_DURATION_SECONDS
        chunk_idx += 1

    return chunks


def merge_transcriptions(texts: list[str]) -> str:
    """Merge transcription chunks into a single text, stripping empty chunks."""
    return " ".join(t.strip() for t in texts if t and t.strip())


def needs_chunking(file_path: Path) -> bool:
    """Return True if file exceeds Groq 25 MB limit."""
    return file_path.stat().st_size > GROQ_MAX_FILE_BYTES
