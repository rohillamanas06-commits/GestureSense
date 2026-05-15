# ✋ GestureSense - AI-Powered Sign Language Recognition

GestureSense is a cutting-edge web application that leverages advanced AI technology to analyze and detect sign language gestures. Built with React, TypeScript, and FastAPI, GestureSense helps users translate hand signs in real-time using their webcam or uploaded images.

### ✨ Key Features

- **🤖 AI-Powered Detection**: Utilizes MediaPipe for hand landmark detection and Scikit-Learn for accurate gesture classification.
- **🎯 Real-time Streaming**: Instant analysis of gestures through high-performance WebSocket streaming.
- **📊 Dataset Driven**: Dynamically trained on the public-domain Sign Language MNIST dataset via Hugging Face.
- **🎨 Modern UI**: Beautiful, responsive interface built with Tailwind CSS v4 and shadcn/ui.
- **⚡ Fast Routing**: Utilizes TanStack Router for lightning-fast, type-safe client-side routing.
- **📱 Mobile Responsive**: Optimized for seamless experience across all device sizes.

---

## 🚀 Tech Stack

### Frontend
- **React 19** - Modern UI library
- **TypeScript 5.8** - Type-safe JavaScript
- **Vite 7** - Lightning-fast build tool
- **Tailwind CSS 4** - Utility-first CSS framework
- **shadcn/ui** - Beautiful, accessible component library
- **TanStack Router & Start** - Type-safe routing framework
- **Lucide React** - Icon library

### Backend
- **FastAPI 0.111.0** - High-performance Python web framework
- **MediaPipe 0.10.11** - Real-time hand landmark detection
- **Scikit-Learn 1.4.2** - Machine learning classification model
- **OpenCV** - Image processing and manipulation
- **Hugging Face Datasets** - Source for Sign Language MNIST
- **Uvicorn** - ASGI Web Server

---

## 📁 Project Structure

```
GestureSense/
├── src/
│   ├── components/        # React components
│   ├── hooks/             # Custom hooks
│   ├── lib/               # Utilities
│   ├── routes/            # TanStack Router routes
│   ├── router.tsx         # Router configuration
│   ├── server.ts          # Server entry point
│   ├── start.ts           # Client entry point
│   └── styles.css         # Global styling
├── public/                # Static assets (to be added)
├── app.py                 # FastAPI backend entry point
├── requirements.txt       # Python dependencies
├── package.json           # Node dependencies
├── vite.config.ts         # Vite configuration
└── tsconfig.json          # TypeScript configuration
```

---

<div align="center">

**Made with ❤️ by Manas Rohilla**

⭐ Star this repo if you find it useful!

</div>
