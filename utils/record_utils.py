"""
Audio helpers for the terminal version (main.py).

sounddevice, scipy, noisereduce and numpy are imported lazily inside the functions that
use them, so the Streamlit app starts on machines without PortAudio.
"""

import threading


def validate_audio_file(filename):
    """Validate audio file has actual content"""
    try:
        import numpy as np
        from scipy.io.wavfile import read

        rate, data = read(filename)

        # Check if data exists and has audio content
        if data is None or len(data) == 0:
            return False

        # Check if audio has actual sound (not just silence)
        if np.max(np.abs(data)) < 100:  # Very quiet threshold
            return False

        return True

    except Exception:
        return False


def record_audio_with_interrupt(filename="recorded.wav", fs=16000):
    """Record audio until user presses Enter to stop"""
    import numpy as np
    import sounddevice as sd
    from scipy.io.wavfile import write

    print("Recording... Press Enter to stop recording.")

    # Flag to control recording
    recording = threading.Event()
    recording.set()

    # Audio data list
    audio_chunks = []

    def audio_callback(indata, frames, time, status):
        if recording.is_set():
            audio_chunks.append(indata.copy())

    # Start recording stream
    stream = sd.InputStream(
        samplerate=fs, channels=1, dtype="int16", callback=audio_callback
    )

    # Thread to listen for Enter key
    def wait_for_enter():
        input()  # Wait for Enter key
        recording.clear()
        stream.stop()

    enter_thread = threading.Thread(target=wait_for_enter)
    enter_thread.daemon = True
    enter_thread.start()

    # Start recording
    with stream:
        enter_thread.join()

    # Combine all audio chunks
    if audio_chunks:
        audio_data = np.concatenate(audio_chunks, axis=0)
        write(filename, fs, audio_data)
        print("Recording stopped.")
    else:
        # Create empty audio file if no data
        write(filename, fs, np.array([], dtype="int16").reshape(0, 1))
        print("No audio recorded.")

    return filename, fs


def reduce_noise(filename, fs):
    """Reduce noise from audio file"""
    import noisereduce as nr
    import numpy as np
    from scipy.io.wavfile import read, write

    rate, data = read(filename)
    if len(data) > 0:
        reduced_noise = nr.reduce_noise(y=data.flatten(), sr=rate)
        write(filename, fs, reduced_noise.astype(np.int16))
    return filename


def save_audio_file(audio_bytes, filename):
    """
    Save audio bytes to a file with the specified filename.

    :param audio_bytes: Audio data in bytes
    :param filename: The full filename with extension
    :return: The name of the saved audio file
    """
    import os

    directory = os.path.dirname(filename)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(filename, "wb") as f:
        f.write(audio_bytes)
    return filename
