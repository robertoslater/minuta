"use client";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/lib/store";

export function Topbar() {
  const { isRecording, backendConnected } = useAppStore();

  return (
    <header className="flex items-center gap-4 border-b border-border px-4 py-4">
      <SidebarTrigger />
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        {isRecording && (
          <Badge variant="destructive" className="animate-pulse gap-1.5 font-mono text-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-white" />
            REC
          </Badge>
        )}
        <Badge
          variant={backendConnected ? "default" : "secondary"}
          className="font-mono text-xs"
        >
          {backendConnected ? "Backend aktiv" : "Offline"}
        </Badge>
      </div>
    </header>
  );
}
