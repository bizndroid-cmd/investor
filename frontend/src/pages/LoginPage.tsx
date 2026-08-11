import { useState } from "react";
import { apiFetch } from "@/api/client";
import { Zap } from "lucide-react";

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export function LoginPage({ onLogin }: { onLogin: () => void }) {
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
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm animate-scale-in">
        <div className="rounded-2xl border bg-card p-8 shadow-xl shadow-primary/5">
          {/* Logo */}
          <div className="flex items-center justify-center gap-2.5 mb-6">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-primary/10">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <span className="text-xl font-bold tracking-tight">Investor</span>
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
                {isRegister ? "Already have an account?" : "Don't have an account?"}{" "}
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(!isRegister);
                    setError(null);
                    setConfirmPassword("");
                  }}
                  className="text-primary font-medium hover:underline transition-colors"
                >
                  {isRegister ? "Sign in" : "Register"}
                </button>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
