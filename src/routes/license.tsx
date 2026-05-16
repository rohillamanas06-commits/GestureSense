export default function License() {
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
                License
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
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold tracking-[0.04em] md:tracking-[0.05em] mb-4">License</h1>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense is licensed under the MIT License, which permits use, modification, and distribution with certain conditions. Please review the full license terms below.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">MIT License</h2>
            <p className="text-muted-foreground leading-relaxed">
              Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Conditions</h2>
            <p className="text-muted-foreground leading-relaxed">
              The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Disclaimer</h2>
            <p className="text-muted-foreground leading-relaxed">
              THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Attribution</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense utilizes several open-source libraries and technologies. We are grateful to the open-source community for their contributions. All third-party licenses are respected and acknowledged.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Open Source Components</h2>
            <p className="text-muted-foreground leading-relaxed">
              GestureSense uses MediaPipe (Apache 2.0), React (MIT), FastAPI (MIT), and scikit-learn (BSD). We maintain compliance with all open-source licenses and acknowledge their contributions to this project.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold tracking-wider mb-4">Full License Text</h2>
            <p className="text-muted-foreground leading-relaxed">
              For the complete MIT License text and additional information about third-party licenses, please refer to the LICENSE file in the GestureSense repository.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
