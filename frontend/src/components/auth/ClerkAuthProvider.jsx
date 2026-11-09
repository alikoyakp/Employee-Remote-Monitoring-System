import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClerkProvider } from "@clerk/react";
import { dark } from "@clerk/ui/themes";

const appearance = {
  theme: dark,
  variables: {
    colorPrimary: "#6A5DA4",
    colorPrimaryForeground: "#FFFFFF",
    colorTextOnPrimaryBackground: "#FFFFFF",
    colorBackground: "#111827",
    colorInput: "#0B0F17",
    fontFamily: "Plus Jakarta Sans, sans-serif",
    borderRadius: "0.6rem",
  },
  captcha: { theme: "dark" },
};

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function ClerkAuthProvider({ children }) {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [unavailable, setUnavailable] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async (attempt = 0) => {
      try {
        const cfg = await (await fetch(`${BACKEND_URL}/api/clerk/config`)).json();
        if (cfg.reason === "invalid_keys") return cancelled || setUnavailable("invalid_keys");
        if (cfg.enabled) {
          // Resolve the relative proxy path against the backend so split frontend/API domains work.
          const proxyUrl = cfg.proxy_url ? new URL(cfg.proxy_url, BACKEND_URL).href : "";
          return cancelled || setConfig({ ...cfg, proxy_url: proxyUrl });
        }
      } catch {}
      if (cancelled) return;
      if (attempt >= 20) return setUnavailable("down");
      setTimeout(() => load(attempt + 1), 1500);
    };
    load();
    return () => { cancelled = true; };
  }, []);

  if (unavailable === "invalid_keys") {
    return (
      <p style={{ padding: 24 }} data-testid="auth-config-error">
        Sign-in is not configured: CLERK_PUBLISHABLE_KEY / CLERK_SECRET_KEY on the server are missing or still placeholders.
        Add your real Clerk keys to backend/.env and restart the backend.
      </p>
    );
  }
  if (unavailable) return <p style={{ padding: 24 }}>Sign-in is unavailable right now. Refresh the page to try again.</p>;
  if (!config) return null;
  return (
    <ClerkProvider
      publishableKey={config.publishable_key}
      proxyUrl={config.proxy_url || undefined}
      appearance={appearance}
      routerPush={(to) => navigate(to)}
      routerReplace={(to) => navigate(to, { replace: true })}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/"
      signUpFallbackRedirectUrl="/"
      afterSignOutUrl="/"
      localization={{
        signIn: { start: { title: "Continue to ERM System", titleCombined: "Continue to ERM System" } },
        signUp: { start: { title: "Create your ERM System account", titleCombined: "Create your ERM System account" } },
      }}
    >
      {children}
    </ClerkProvider>
  );
}
