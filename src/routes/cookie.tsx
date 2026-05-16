export default function Cookie() {
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
                Cookie Policy
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
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold tracking-[0.04em] md:tracking-[0.05em] mb-4">Cookie Policy</h1>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense uses cookies to enhance your experience and provide essential functionality. This policy explains what cookies are, how we use them, and your options regarding their use.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">What Are Cookies?</h2>
            <p className="text-muted-foreground leading-relaxed">
              Cookies are small files stored on your device that contain information about your browsing preferences and activity. They allow websites to remember your choices and provide a more personalized experience.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">How We Use Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense uses cookies for the following purposes:
            </p>
            <ul className="text-muted-foreground leading-relaxed list-disc list-inside space-y-2 mt-2">
              <li>Session Management: To maintain your login session and preferences</li>
              <li>Functionality: To remember your settings and configuration choices</li>
              <li>Performance: To analyze site performance and improve user experience</li>
              <li>Security: To protect your account and detect suspicious activity</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Types of Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              <strong>Essential Cookies:</strong> These are necessary for the website to function properly. They enable core functionality like session management and security features.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              <strong>Preference Cookies:</strong> These remember your choices, such as language preferences and display settings, to provide a personalized experience.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-3">
              <strong>Analytics Cookies:</strong> These help us understand how users interact with our site to improve functionality and user experience.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Managing Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              You can control cookies through your browser settings. Most browsers allow you to refuse cookies or alert you when cookies are being sent. However, disabling essential cookies may affect the functionality of GestureSense. We recommend keeping essential cookies enabled for the best experience.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Third-Party Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense does not use third-party cookies for tracking or advertising purposes. Any third-party services integrated with our platform are subject to their own cookie policies.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Contact Us</h2>
            <p className="text-muted-foreground leading-relaxed">
              If you have questions about our cookie practices, please contact us through our website. We are happy to provide additional information about how we use cookies.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
