"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/providers/Auth";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const router = useRouter();
  const { signOut } = useAuth();

  const logout = async () => {
    await signOut();
    router.push("/auth/login");
  };

  return <Button onClick={logout}>Sign out</Button>;
}
