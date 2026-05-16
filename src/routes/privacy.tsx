import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/privacy")({ component: Privacy });

function Privacy() {
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
                Privacy Policy
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
            <h1 className="text-3xl md:text-4xl font-bold tracking-[0.05em] mb-4">Privacy Policy</h1>
            <p className="text-muted-foreground leading-relaxed">
              At GestureSense, we are committed to protecting your privacy and ensuring you have a positive experience on our platform.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Data Collection</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense operates with local inference, meaning all processing happens on your device. We do not collect, store, or transmit video data, images, or gesture information to external servers. Your hand gestures and camera feed remain entirely on your machine and are never sent to our servers.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Local Processing</h2>
            <p className="text-muted-foreground leading-relaxed">
              All gesture detection and analysis is performed locally on your device using MediaPipe and our machine learning models. No personal data is transmitted over the internet, ensuring complete privacy and control over your information.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Cookies and Tracking</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may use cookies for essential functionality like session management and user preferences. We do not use tracking cookies or third-party analytics that would compromise your privacy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Security</h2>
            <p className="text-muted-foreground leading-relaxed">
              Since data processing occurs locally on your device, security is inherently protected by your device's security measures. We recommend keeping your browser and operating system updated with the latest security patches.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Third-Party Services</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense does not integrate with third-party tracking services or share user data with external parties. The application operates independently to protect your privacy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Contact Us</h2>
            <p className="text-muted-foreground leading-relaxed">
              If you have questions about our privacy practices, please contact us through our website. We are committed to addressing your concerns promptly.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
