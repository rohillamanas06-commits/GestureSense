import { useEffect, useState } from "react";

import About from "./routes/about";
import Cookie from "./routes/cookie";
import FAQ from "./routes/faq";
import Home from "./routes/index";
import License from "./routes/license";
import Privacy from "./routes/privacy";
import Terms from "./routes/terms";

const routeMap = {
  "/": Home,
  "/about": About,
  "/cookie": Cookie,
  "/faq": FAQ,
  "/license": License,
  "/privacy": Privacy,
  "/terms": Terms,
} as const;

type RoutePath = keyof typeof routeMap;

const pageTitles: Record<RoutePath, string> = {
  "/": "GestureSense — Sign Language Detection",
  "/about": "About — GestureSense",
  "/cookie": "Cookie Policy — GestureSense",
  "/faq": "FAQ — GestureSense",
  "/license": "License — GestureSense",
  "/privacy": "Privacy Policy — GestureSense",
  "/terms": "Terms of Service — GestureSense",
};

function isRoutePath(pathname: string): pathname is RoutePath {
  return pathname in routeMap;
}

function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you&apos;re looking for does not exist or has been moved.
        </p>
        <div className="mt-6">
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const handlePopState = () => {
      setPathname(window.location.pathname);
    };

    const handleClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.altKey ||
        event.ctrlKey ||
        event.shiftKey
      ) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) return;

      const anchor = target.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target || anchor.hasAttribute("download")) return;

      const url = new URL(anchor.href, window.location.origin);
      if (url.origin !== window.location.origin) return;

      event.preventDefault();
      window.history.pushState({}, "", `${url.pathname}${url.search}${url.hash}`);
      setPathname(url.pathname);
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    };

    window.addEventListener("popstate", handlePopState);
    window.addEventListener("click", handleClick);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      window.removeEventListener("click", handleClick);
    };
  }, []);

  useEffect(() => {
    document.title = isRoutePath(pathname) ? pageTitles[pathname] : "GestureSense";
  }, [pathname]);

  const Page = isRoutePath(pathname) ? routeMap[pathname] : NotFoundPage;

  return <Page />;
}