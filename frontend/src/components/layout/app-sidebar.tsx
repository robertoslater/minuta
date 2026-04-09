"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  Mic,
  LayoutDashboard,
  Clock,
  Settings,
  Moon,
  Sun,
  PanelLeft,
} from "lucide-react";
import { useTheme } from "next-themes";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { PlanBadge } from "@/components/pro-gate";
import { useAppStore } from "@/lib/store";

const navItems = [
  { title: "Dashboard", href: "/", icon: LayoutDashboard },
  { title: "Aufnahme", href: "/record", icon: Mic },
  { title: "Meetings", href: "/meetings", icon: Clock },
  { title: "Einstellungen", href: "/settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { isRecording } = useAppStore();
  const { state, toggleSidebar } = useSidebar();
  const isCollapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b px-3 py-4">
        <Link href="/" className="flex items-center justify-start">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt="Minuta"
            width={32}
            height={32}
            className="h-8 w-8 shrink-0 object-contain"
          />
          {!isCollapsed && (
            <div className="flex flex-col ml-2.5">
              <span className="text-base font-semibold tracking-tight leading-tight">
                Minu<span className="text-primary">ta</span>
              </span>
              <span className="text-[10px] text-muted-foreground leading-tight">
                by Moro Vision GmbH
              </span>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          {!isCollapsed && (
            <SidebarGroupLabel className="font-mono text-[10px] uppercase tracking-wider">
              Navigation
            </SidebarGroupLabel>
          )}
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    render={<Link href={item.href} />}
                    isActive={pathname === item.href}
                    tooltip={item.title}
                  >
                    <item.icon className="h-4 w-4" />
                    <span>{item.title}</span>
                    {item.href === "/record" && isRecording && (
                      <span className="ml-auto h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                    )}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-2 space-y-1">
        {!isCollapsed && (
          <div className="px-2 py-1">
            <PlanBadge />
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4 shrink-0" />
          ) : (
            <Moon className="h-4 w-4 shrink-0" />
          )}
          {!isCollapsed && (
            <span className="text-xs">
              {theme === "dark" ? "Light Mode" : "Dark Mode"}
            </span>
          )}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={toggleSidebar}
        >
          <PanelLeft className="h-4 w-4 shrink-0" />
          {!isCollapsed && (
            <span className="text-xs">Minimieren</span>
          )}
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}
