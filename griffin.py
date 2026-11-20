import os

import sounddevice as sd
import soundfile as sf
import requests
import subprocess
import numpy as np
import time

# ==================================
# GRIFFIN DESKTOP CONFIGURATION
# ==================================

WEBHOOK_URL = os.getenv("GRIFFIN_WEBHOOK_URL", "")
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

MIC = 2
SPEAKER = 5

SAMPLE_RATE = int(sd.query_devices(MIC)["default_samplerate"])

SILENCE_LIMIT = 1.2
MAX_DURATION = 20
START_TIMEOUT = 10
THRESHOLD = 0.012

# ==================================
# AUTOMATIC VOICE DETECTION
# ==================================

def listen():

    print("\nGriffin is listening... Speak whenever you're ready.")

    chunk_duration = 0.03
    chunk_size = int(SAMPLE_RATE * chunk_duration)

    frames = []
    speaking = False
    silence_time = 0
    elapsed = 0

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=MIC,
            blocksize=chunk_size
        ) as stream:

            while elapsed < MAX_DURATION:

                audio, overflowed = stream.read(chunk_size)

                level = float(np.sqrt(np.mean(audio ** 2)))

                elapsed += chunk_duration

                if level > THRESHOLD:

                    if not speaking:
                        print("I can hear you...")
                        speaking = True

                    silence_time = 0
                    frames.append(audio.copy())

                elif speaking:

                    frames.append(audio.copy())
                    silence_time += chunk_duration

                    if silence_time >= SILENCE_LIMIT:
                        break

                elif elapsed >= START_TIMEOUT:

                    print("I didn't hear anything. Try again.")
                    return False

        if not frames:
            return False

        recording = np.concatenate(frames, axis=0)

        sf.write(
            "griffin_input.wav",
            recording,
            SAMPLE_RATE
        )

        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i", "griffin_input.wav",
                "-c:a", "aac",
                "-b:a", "128k",
                "griffin_input.m4a"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        print("Recording complete.")
        return True

    except Exception as error:

        print("Microphone error:", error)
        return False


# ==================================
# SEND VOICE TO GRIFFIN'S BRAIN
# ==================================

def talk():

    print("\nSending your voice to Griffin...")

    try:

        with open("griffin_input.m4a", "rb") as audio:

            response = requests.post(
                WEBHOOK_URL,
                files={
                    "audio0": (
                        "griffin.m4a",
                        audio,
                        "audio/mp4"
                    )
                },
                timeout=180
            )

        response.raise_for_status()

        with open("griffin_response.mp3", "wb") as file:
            file.write(response.content)

        if not response.content:
            raise Exception("Griffin returned an empty audio response.")

        print("\nGriffin is responding...")

        # Convert MP3 into WAV for playback

        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i", "griffin_response.mp3",
                "-f", "wav",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "griffin_response.wav"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

        audio_data, rate = sf.read(
            "griffin_response.wav",
            dtype="float32"
        )

        sd.play(
            audio_data,
            rate,
            device=SPEAKER
        )

        sd.wait()

        print("\nGriffin has finished speaking.")

    except requests.exceptions.RequestException as error:

        print("\nConnection error:", error)

    except Exception as error:

        print("\nSomething went wrong:", error)


# ==================================
# MAIN DESKTOP LOOP
# ==================================

print("================================")
print("       GRIFFIN DESKTOP")
print("================================")
print("Automatic voice detection enabled.")
print("Speak naturally. Press Ctrl+C to exit.")

try:

    while True:

        if listen():
            talk()

        time.sleep(0.2)

except KeyboardInterrupt:

    print("\nGriffin Desktop shutting down.")

