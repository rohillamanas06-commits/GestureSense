import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/faq")({ component: FAQ });

function FAQ() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-background/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="size-9 border border-cyan-soft bg-cyan-soft flex items-center justify-center text-cyan text-xs">
              <span className="font-bold">[ ]</span>
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-wider">
                <span className="text-cyan">GESTURE</span><span>SENSE</span>
              </div>
              <div className="text-[10px] text-muted-foreground tracking-[0.18em] uppercase mt-0.5">
                FAQ
              </div>
            </div>
          </div>

          <a
            href="/"
            className="text-muted-foreground hover:text-cyan transition-colors text-xs uppercase tracking-widest"
          >
            Back to Console
          </a>
        </div>
      </header>

      <main className="max-w-[1000px] mx-auto px-6 py-12">
        <div className="space-y-6">
          <section>
            <h1 className="text-3xl md:text-4xl font-bold tracking-[0.05em] mb-4">Frequently Asked Questions</h1>
            <p className="text-muted-foreground leading-relaxed">
              Find answers to common questions about GestureSense and how to use it effectively.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">What is GestureSense?</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense is a real-time sign language detection system powered by machine learning and computer vision. It recognizes hand gestures from your webcam or uploaded images, making sign language communication more accessible and interactive.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">How does GestureSense work?</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense uses MediaPipe to extract hand landmarks from video frames, then applies a Random Forest machine learning model to classify gestures. All processing happens locally on your device, ensuring privacy and minimal latency.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Do I need to install anything?</h2>
            <p className="text-muted-foreground leading-relaxed">
              No installation is required. GestureSense runs directly in your web browser. Simply access the application through your browser and grant camera permissions when prompted.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Is my camera data stored or transmitted?</h2>
            <p className="text-muted-foreground leading-relaxed">
              No. GestureSense performs all processing locally on your device. Your camera feed and gesture data are never stored, transmitted, or accessed by external servers. Your privacy is completely protected.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">What gestures can GestureSense recognize?</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense is trained on the Sign MNIST dataset and can recognize a comprehensive set of sign language gestures. The system is continuously improved to support more gestures and variations.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">What are the system requirements?</h2>
            <p className="text-muted-foreground leading-relaxed">
              You need a modern web browser with WebSocket support and camera access. GestureSense works on Windows, macOS, and Linux. We recommend a device with a webcam for real-time detection.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">What is the detection latency?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Processing latency typically ranges from 100 to 400 milliseconds depending on your system resources. This latency can be configured through the application settings for optimal performance on your device.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Can I export my detection history?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Yes. GestureSense maintains a detection history log with timestamps and confidence scores. You can view and review your detection history directly in the application interface.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Is GestureSense free to use?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Yes, GestureSense is completely free to use. It is released under the MIT License, allowing free and open use for personal and commercial projects.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">How do I get support?</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions, bug reports, or feature requests, please visit our GitHub repository or contact us through our website. We are committed to providing support and improving GestureSense based on user feedback.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Can I contribute to GestureSense?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Absolutely! GestureSense is an open-source project and welcomes contributions. You can contribute by reporting bugs, suggesting features, submitting pull requests, or helping improve documentation.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
