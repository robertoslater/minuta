"use client";

import { useEffect } from "react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Topbar } from "@/components/layout/topbar";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const setBackendConnected = useAppStore((s) => s.setBackendConnected);
  const setLicense = useAppStore((s) => s.setLicense);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await api.health();
        setBackendConnected(true);
      } catch {
        setBackendConnected(false);
      }
    };

    const checkLicense = async () => {
      try {
        const lic = await api.getLicense();
        setLicense(lic.is_pro, lic.plan);
      } catch {}
    };

    checkHealth();
    checkLicense();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [setBackendConnected, setLicense]);

  return (
    <SidebarProvider>
      <AppSidebar />
      <main className="flex-1 flex flex-col min-h-screen">
        <Topbar />
        <div className="flex-1 p-6">{children}</div>
      </main>
    </SidebarProvider>
  );
}
