# AuraFrame

AuraFrame is a Raspberry Pi display that shows what's playing in your room. It listens to ambient audio, identifies songs in real-time, and displays album art with track info. When there's no music, it becomes a photo frame.

No integrations, no pairing, no apps to install. If you can hear it, AuraFrame can identify it.

---

## Why This Exists

Most "now playing" displays need direct integration with your devices (e.g. Spotify API, Bluetooth, AirPlay). That breaks down fast when you have multiple/incompatible audio sources or guests want to play music.

AuraFrame just listens to the room and figures it out:

- Works with your turntable, phone, TV, or any other audio source
- No accounts or ecosystem lock-in
- Stays useful when idle (photo slideshow)
- Simple privacy control when you want it off

It's designed to sit quietly in a room and look intentional, not demanding.

---

## What It Does

- Passively identifies music from microphone audio
- Displays album art, title, artist, album, and year
- Shows a subtle status indicator (listening vs. playing)
- Auto-switches to slideshow when the room goes quiet
- Touch the screen to reveal **Start/Stop Listening** control
- Clean, high-contrast layout designed for viewing from across the room

---

## Privacy Control

Tap the screen to reveal a **Start/Stop Listening** button. When you stop listening:

- Microphone recording is disabled
- No recognition requests are made
- Display switches to slideshow-only mode
- No audio is captured or uploaded

Useful when you want guaranteed privacy, the room is noisy but not musical, or you just want a picture frame for a while.

---

## How It Works

1. Records short audio snippets from a microphone (when enabled)
2. Fingerprints and identifies the audio using music recognition
3. Updates the display when a match is found
4. Switches to slideshow after extended silence
5. Returns to "now playing" when music resumes

The system avoids constant re-rendering to keep the display calm and flicker-free.

---

## Hardware

Built for Raspberry Pi, but runs on any Linux machine with:

- A microphone (USB or HAT)
- A display (HDMI, touchscreen, etc.)
- Network access for recognition

Typical setup:
- Raspberry Pi 4
- USB microphone
- 12" HDMI touchscreen

---

## Stack

- **Python 3**
- **pygame** for rendering
- **Pillow** for layout and image processing
- **sounddevice** for audio capture
- **shazamio** for music recognition
- Threading and asyncio for non-blocking recognition

---

## Setup

> Full setup guide coming soon

1. Install system dependencies (PortAudio, Inter fonts, etc.)
2. Create a Python virtual environment
3. Install Python packages from `requirements.txt`
4. Configure audio device index
5. Add slideshow images to `slideshow/` directory
6. Run fullscreen

Check the config section at the top of the script to tune behavior.

---

## Configuration

Everything's configurable via constants at the top of the script:

- How often to attempt recognition
- Audio sensitivity threshold
- Idle time before slideshow kicks in
- Slideshow directory and timing
- UI spacing and fonts

No config files, just change the values and restart.

---

## Current State

This is a personal project that's working well but still evolving. Core functionality is solid, but these areas are rough:

- Long-term stability and auto-recovery from audio/network issues
- Packaging (systemd service, disk image, etc.)
- Setup documentation
- Testing on different hardware

If you try this and run into issues, that's expected. PRs welcome.

---

## Why "AuraFrame"?

It captures and adds to the *aura* of the room (the music, the mood, the atmosphere). Plus it sounds better than "ShazamPiFrameThing."

---

## License

MIT. Use it however you want. Attribution is nice but not required.

---

## Inspiration

I wanted a "now playing" display that could pick up music from our turntable, phones, TV, whatever. So I built one.

If that sounds useful to you, feel free to clone it or make it your own.
