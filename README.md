#  GestureSense - Sign Language Detection Console

GestureSense is a modern sign-language detection app with a sleek TanStack Start frontend and a FastAPI backend powered by a configurable vision model. It supports live webcam detection, single-image uploads, and a real-time detection log for quick feedback.

##  Screenshots

![GestureSense screenshot](public/Screenshot%202026-05-16%20145005.png)
![GestureSense screenshot](public/Screenshot%202026-05-16%20161019.png)
![GestureSense screenshot](public/about.png)



##  Features

- 🎨 **Modern Console UI** - Clean, futuristic interface with real-time status indicators
- 🤖 **AI Gesture Detection** - Gemini Vision or Groq Llama vision inference for uploaded images and webcam frames
- 📹 **Live Camera Stream** - Real-time detection through a websocket-driven webcam feed
- 🖼️ **Image Upload** - Single-frame gesture detection from image files
- 📊 **Detection Log** - Track recognized signs with timestamps and confidence scores
- ⚡ **Fast Status Checks** - Health endpoint keeps the frontend aware of backend/model readiness
- 📱 **Responsive Layout** - Works across desktop and mobile screen sizes

##  Tech Stack

### Frontend
- **Framework:** TanStack Start + React
- **Language:** TypeScript
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **UI Components:** Radix UI + custom components
- **Routing:** TanStack Router
- **State/Data:** React state hooks + TanStack Query

### Backend
- **Framework:** FastAPI (Python)
- **AI Integration:** Google Generative AI / Gemini Vision or Groq Llama vision
- **Realtime:** WebSocket streaming for live camera frames
- **CORS:** Enabled for local frontend development
- **Environment Loading:** python-dotenv

### Deployment

#### Backend (Render)
1. Push code to GitHub
2. Connect your repository to Render
3. Select `render.yaml` as the configuration
4. Set environment variables (GEMINI_API_KEY, GROQ_API_KEY, VISION_PROVIDER)
5. Deploy — Render will automatically build and run the FastAPI server

#### Frontend (Vercel)
1. Push code to GitHub
2. Import project in Vercel dashboard
3. Set `VITE_API_URL` environment variable to your Render backend URL
4. Deploy — Vercel will build and deploy the TanStack frontend

#### Local Setup
1. Clone the repository
2. Install backend dependencies: `pip install -r requirements.txt`
3. Install frontend dependencies: `npm install`
4. Create `.env` file (see `.env.example`)
5. Run backend: `python gesturesense.py`
6. Run frontend: `npm run dev`

## 📂 Project Structure

```text
GestureSense/
├── src/
│   ├── components/
│   │   └── ui/
│   ├── hooks/
│   ├── lib/
│   ├── routes/
│   │   ├── __root.tsx
│   │   ├── index.tsx
│   │   ├── about.tsx
│   │   ├── faq.tsx
│   │   ├── privacy.tsx
│   │   ├── terms.tsx
│   │   ├── cookie.tsx
│   │   └── license.tsx
│   ├── router.tsx
│   ├── server.ts
│   └── styles.css
├── public/
├── gesturesense.py
├── requirements.txt
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```


Made with ❤️ by Manas Rohilla
