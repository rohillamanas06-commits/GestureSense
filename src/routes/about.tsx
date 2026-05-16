export default function About() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-background/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-[1400px] mx-auto px-4 md:px-6 min-h-16 py-2 md:py-0 flex flex-wrap items-center justify-between gap-3 md:gap-4">
          <div className="flex items-center gap-3">
            <div className="size-9 border border-cyan-soft bg-cyan-soft flex items-center justify-center text-cyan text-xs">
              <span className="font-bold">[ ]</span>
            </div>
            <div className="leading-tight">
              <div className="text-xs sm:text-sm font-semibold tracking-wider">
                <span className="text-cyan">GESTURE</span><span>SENSE</span>
              </div>
              <div className="text-[9px] sm:text-[10px] text-muted-foreground tracking-[0.14em] sm:tracking-[0.18em] uppercase mt-0.5">
                About
              </div>
            </div>
          </div>

          <a
            href="/"
            className="text-muted-foreground hover:text-cyan transition-colors text-[10px] sm:text-xs uppercase tracking-[0.14em] sm:tracking-widest"
          >
            Back to Console
          </a>
        </div>
      </header>

      <main className="max-w-[1000px] mx-auto px-4 md:px-6 py-8 md:py-12">
        <div className="space-y-6">
          <section>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold tracking-[0.04em] md:tracking-[0.05em] mb-4">About GestureSense</h1>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense is a real-time sign language detection system powered by machine learning and computer vision. It enables instant recognition of hand gestures through live camera feed or image upload, making sign language communication more accessible and interactive.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Technology Stack</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense leverages MediaPipe for advanced hand landmark detection and pose estimation, enabling precise identification of hand positions and finger movements. The system uses a Random Forest Classifier machine learning model to analyze these landmarks and identify specific gestures with high accuracy. The backend is powered by FastAPI, providing a high-performance REST API and WebSocket streaming for real-time communication. The frontend is built with React, delivering a modern, responsive web interface with real-time updates.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Features</h2>
            <p className="text-muted-foreground leading-relaxed">
              The system supports live camera stream with real-time gesture detection, allowing users to see results instantly as they perform hand gestures. Configurable latency settings enable performance optimization based on system resources and user preferences. A comprehensive detection history log records all recognized gestures with timestamps and confidence scores for review and analysis. The local inference approach ensures minimal latency and privacy, as all processing happens on the user's machine.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">How It Works</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense operates through a four-step process. First, the camera captures hand gestures in real-time from the video feed. Next, MediaPipe extracts hand landmarks and finger positions, creating a detailed map of the hand structure. The Random Forest model then analyzes these landmarks to classify the gesture. Finally, results are displayed with confidence scores and timestamps, logged to the detection history for reference.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">System Requirements</h2>
            <p className="text-muted-foreground leading-relaxed">
              The backend requires Python 3.8 or higher, along with FastAPI, MediaPipe, and scikit-learn libraries. The frontend operates in any modern web browser with WebSocket support and requires camera and microphone permissions. Processing latency typically ranges from 100 to 400 milliseconds depending on system resources and the selected frame sampling interval.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
