"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";

import { cn } from "@/lib/utils";
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

function UpdatePasswordFormContent({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"div">) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const username = searchParams.get("username") ?? "";
  const code = searchParams.get("code") ?? "";
  const { confirmResetPassword } = useAuth();

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    if (!username || !code) {
      setError("Invalid reset link");
      setIsLoading(false);
      return;
    }

    try {
      const { error } = await confirmResetPassword(username, code, password);
      if (error) throw new Error(error);
      router.push("/auth/login");
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : "An error occurred");
    } finally {
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
            Reset Your Password
          </CardTitle>
          <CardDescription>
            Please enter your new password below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpdatePassword}>
            <input
              type="hidden"
              name="username"
              value={username}
            />
            <input
              type="hidden"
              name="code"
              value={code}
            />
            <div className="flex flex-col gap-6">
              <div className="grid gap-2">
                <Label htmlFor="password">New password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="New password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? "Saving..." : "Save new password"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export function UpdatePasswordForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"div">) {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <UpdatePasswordFormContent
        className={className}
        {...props}
      />
    </Suspense>
  );
}
