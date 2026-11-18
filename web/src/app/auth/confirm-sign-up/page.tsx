"use client";

export const dynamic = "force-dynamic";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/providers/Auth";
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

// useSearchParams requires a Suspense boundary under static export, hence
// the ConfirmSignUpCard split.
function ConfirmSignUpCard() {
  const params = useSearchParams();
  const [username, setUsername] = useState(params.get("username") ?? "");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const router = useRouter();
  const { confirmSignUp, resendSignUpCode } = useAuth();

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const { error } = await confirmSignUp(username, code);
      if (error) throw new Error(error);
      setSuccess(true);
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    setError(null);
    try {
      const { error } = await resendSignUpCode(username);
      if (error) throw new Error(error);
    } catch (error: unknown) {
      setError(
        error instanceof Error ? error.message : "Failed to resend code",
      );
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-medium tracking-normal">
          {success ? "Account Confirmed" : "Confirm Your Account"}
        </CardTitle>
        <CardDescription>
          {success
            ? "Your account has been confirmed. You can now sign in."
            : "Enter the confirmation code sent to your email"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {success ? (
          <div className="flex flex-col gap-4">
            <p className="text-muted-foreground text-sm">
              Your account has been successfully confirmed.
            </p>
            <Button
              className="w-full"
              onClick={() => router.push("/auth/login")}
            >
              Sign in
            </Button>
          </div>
        ) : (
          <form onSubmit={handleConfirm}>
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
                <Label htmlFor="code">Confirmation Code</Label>
                <Input
                  id="code"
                  type="text"
                  placeholder="123456"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? "Confirming..." : "Confirm"}
              </Button>
            </div>
            <div className="mt-4 text-center text-sm">
              Didn't receive the code?{" "}
              <Button
                type="button"
                variant="link"
                className="h-auto p-0"
                onClick={handleResend}
                disabled={isLoading}
              >
                Resend code
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
}

export default function ConfirmSignUpPage() {
  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <Suspense fallback={null}>
          <ConfirmSignUpCard />
        </Suspense>
      </div>
    </div>
  );
}
