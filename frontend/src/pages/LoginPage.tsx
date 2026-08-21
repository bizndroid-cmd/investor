import { useState } from "react";
import { apiFetch } from "@/api/client";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export function LoginPage({ onLogin, onRegister }: { onLogin: () => void; onRegister?: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [pendingApproval, setPendingApproval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (isRegister && password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);

    try {
      if (isRegister) {
        await apiFetch("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        setPendingApproval(true);
        setLoading(false);
        return;
      }

      const tokens = await apiFetch<AuthTokens>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      onLogin();
    } catch (err: any) {
      const msg =
        err?.body?.detail || err?.message || "Authentication failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-primary/5 p-4">
      <div className="w-full max-w-sm animate-scale-in">
        <div className="rounded-3xl border bg-card/95 backdrop-blur-sm p-8 shadow-2xl shadow-primary/10">
          {/* Logo */}
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="flex items-center justify-center h-14 w-14 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-500 shadow-xl shadow-blue-500/25">
              <span className="text-white font-black text-lg">₹$</span>
            </div>
            <div>
              <span className="text-2xl font-extrabold tracking-tight">
                <span className="bg-gradient-to-r from-blue-500 to-blue-600 bg-clip-text text-transparent">Ru</span><span className="bg-gradient-to-r from-emerald-500 to-emerald-600 bg-clip-text text-transparent">Do</span>
              </span>
              <p className="text-[10px] text-muted-foreground mt-0.5">by <span className="font-medium">BizNDroid</span></p>
            </div>
          </div>

          {pendingApproval ? (
            <div className="text-center space-y-4">
              <div className="h-12 w-12 mx-auto rounded-full bg-amber-500/10 flex items-center justify-center">
                <span className="text-2xl">⏳</span>
              </div>
              <div>
                <p className="text-sm font-medium">Registration submitted!</p>
                <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                  Your account is pending admin approval. You'll be able to sign in once approved.
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setPendingApproval(false); setIsRegister(false); }}
                className="text-xs text-primary font-medium hover:underline"
              >
                Back to Sign In
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground text-center mb-6">
                {isRegister ? "Create your account" : "Sign in to continue"}
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-xs font-medium mb-1.5 text-muted-foreground">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-xs font-medium mb-1.5 text-muted-foreground">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field"
                    placeholder="Min 8 characters"
                    autoComplete={isRegister ? "new-password" : "current-password"}
                  />
                </div>

                {isRegister && (
                  <div>
                    <label htmlFor="confirmPassword" className="block text-xs font-medium mb-1.5 text-muted-foreground">
                      Confirm Password
                    </label>
                    <input
                      id="confirmPassword"
                      type="password"
                      required
                      minLength={8}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="input-field"
                      placeholder="Repeat password"
                      autoComplete="new-password"
                    />
                  </div>
                )}

                {error && (
                  <p className="text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2" role="alert">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="h-3.5 w-3.5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                      Please wait…
                    </span>
                  ) : (
                    isRegister ? "Create Account" : "Sign In"
                  )}
                </button>
              </form>

              <p className="mt-5 text-center text-xs text-muted-foreground">
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => onRegister ? onRegister() : setIsRegister(true)}
                  className="text-primary font-medium hover:underline transition-colors"
                >
                  Get Started
                </button>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
