"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";
import { safeNextPath } from "@/lib/safe-next-path";
import { useAuth } from "@/providers/Auth";
import { useTurnstileToken } from "@/components/turnstile-widget";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";

type LoginFormProps = React.ComponentPropsWithoutRef<"div"> & {
  captchaToken?: string | null;
  captchaElement?: ReactNode;
  onCaptchaConsumed?: () => void;
};

export function LoginForm({
  className,
  captchaToken: providedToken,
  captchaElement: providedElement,
  onCaptchaConsumed,
  ...props
}: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { signIn } = useAuth();
  const hasSharedCaptcha =
    providedToken !== undefined || providedElement !== undefined;
  const internal = useTurnstileToken("signin", {
    enabled: !hasSharedCaptcha,
  });
  const captchaToken = providedToken ?? internal.token;
  const captchaElement = providedElement ?? internal.element;
  const resetCaptcha = () => {
    internal.reset();
    onCaptchaConsumed?.();
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const { error, challengeName } = await signIn(
        username,
        password,
        captchaToken ?? undefined,
      );
      if (error) throw new Error(error);
      if (challengeName) {
        // Handle MFA challenge if needed
        router.push(`/auth/mfa?challenge=${challengeName}`);
        return;
      }
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(safeNextPath(next, "/"));
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : "An error occurred");
    } finally {
      resetCaptcha();
      setIsLoading(false);
    }
  };

  return (
    <div
      className={cn("flex flex-col gap-6", className)}
      {...props}
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-medium tracking-normal">
            Sign in
          </CardTitle>
          <CardDescription>
            Enter your username and password to sign in to your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin}>
            <div className="flex flex-col gap-6">
              <div className="grid gap-2">
                <Label htmlFor="username">Email</Label>
                <Input
                  id="username"
                  type="email"
                  placeholder="m@example.com"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <div className="flex items-center">
                  <Label htmlFor="password">Password</Label>
                  <Link
                    href="/auth/forgot-password"
                    className="ml-auto inline-block text-sm underline-offset-4 hover:underline"
                  >
                    Forgot your password?
                  </Link>
                </div>
                <Input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              {captchaElement}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? "Signing in..." : "Sign in"}
              </Button>
            </div>
            <div className="mt-4 text-center text-sm">
              Don&apos;t have an account?{" "}
              <Link
                href="/auth/sign-up"
                className="underline underline-offset-4"
              >
                Sign up
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
