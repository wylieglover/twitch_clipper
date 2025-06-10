# TwitchTok (Twitch Clipper) 🎬

![image](https://github.com/user-attachments/assets/709af948-5cf5-4c6f-a2db-36338ccc56be)

**TwitchTok** is an AI-powered Twitch clip editor and automation tool that helps you generate, process, and format Twitch highlights for TikTok, YouTube Shorts, and Instagram Reels.

With a sleek Flutter web UI and a FastAPI Python backend, it automates the workflow for streamers and content creators.

---

## ✨ Features

- **Smart Clip Detection:** Automatically finds and extracts the most hype moments from Twitch VODs or clips.
- **Vertical Video Conversion:** Effortlessly convert horizontal Twitch clips into TikTok-friendly vertical videos, with background blur and resizing.
- **Transcript & Subtitles:** Generate transcripts and optional subtitles using AI.
- **Batch Download & Session Management:** Download individual clips or full sessions as ZIP archives.
- **AI Tagging & Hashtags:** Get auto-generated tags and hashtags for improved social reach.
- **One-Click TikTok Upload (beta):** Instantly upload your best moments to TikTok (and Reels/Shorts soon).
- **Full Local Processing:** All heavy video tasks run locally for speed—no expensive cloud GPUs required!
- **Modern, Responsive UI:** Built with Flutter for web and desktop.

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/wylieglover/twitch_clipper.git
cd twitch_clipper
```

### 2. Setup Environment Variables

Copy the `.env.example` in `backend/` to `.env` and fill in your API keys and secrets:

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env` with your credentials.

### 3. Build and Run with Docker Compose

```bash
docker-compose up --build
```

- The backend runs on http://localhost:8000 (FastAPI)
- The frontend runs on http://localhost:8080 (Flutter web)

### 4. Access the App

Open http://localhost:8080 in your browser.

---

## 🛠️ Technologies

- Flutter (Frontend)
- Python FastAPI (Backend)
- FFmpeg, OpenAI Whisper, PyTorch (AI Video/Audio)
- Docker & Docker Compose (Deployment)

---

## 🙌 Contributing

Contributions are welcome!

Feel free to open issues, submit pull requests, or suggest features.

## 📄 License

MIT License. See LICENSE for details.

---

Made for streamers, editors, and meme lords everywhere.
