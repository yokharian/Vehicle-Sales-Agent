"use client";

import React from "react";
import { useSearchParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Page() {
  return (
    <React.Suspense fallback={null}>
      <ErrorCard />
    </React.Suspense>
  );
}

function ErrorCard() {
  const params = useSearchParams();

  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg font-medium tracking-normal">
                Sorry, something went wrong.
              </CardTitle>
            </CardHeader>
            <CardContent>
              {params?.get("error") ? (
                <p className="text-muted-foreground text-sm">
                  Code error: {params.get("error")}
                </p>
              ) : (
                <p className="text-muted-foreground text-sm">
                  An unspecified error occurred.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
