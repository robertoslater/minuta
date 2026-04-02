"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Mic, Clock, FileText, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, type Meeting } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { formatDuration, formatDate } from "@/lib/format";

export default function DashboardPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const { backendConnected } = useAppStore();

  useEffect(() => {
    if (!backendConnected) return;
    api
      .listMeetings({ limit: 5 })
      .then(setMeetings)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [backendConnected]);

  const totalMeetings = meetings.length;
  const totalDuration = meetings.reduce((sum, m) => sum + m.duration_seconds, 0);
  const withSummary = meetings.filter((m) => m.has_summary).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground text-sm">
          Meeting Transkription & Zusammenfassung
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Meetings"
          value={String(totalMeetings)}
          icon={Clock}
          description="Total aufgezeichnet"
        />
        <StatsCard
          title="Gesamtdauer"
          value={formatDuration(totalDuration)}
          icon={Mic}
          description="Aufnahmezeit"
        />
        <StatsCard
          title="Zusammenfassungen"
          value={String(withSummary)}
          icon={FileText}
          description="Generiert"
        />
        <StatsCard
          title="Status"
          value={backendConnected ? "Aktiv" : "Offline"}
          icon={Zap}
          description="Backend"
        />
      </div>

      {/* Quick Actions */}
      <div className="flex gap-3">
        <Link href="/record" className={buttonVariants()}>
          <Mic className="mr-2 h-4 w-4" />
          Neue Aufnahme
        </Link>
        <Link href="/meetings" className={buttonVariants({ variant: "outline" })}>
          Alle Meetings
        </Link>
      </div>

      {/* Recent Meetings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Letzte Meetings</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Laden...</p>
          ) : meetings.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Noch keine Meetings aufgezeichnet. Starte deine erste Aufnahme!
            </p>
          ) : (
            <div className="space-y-3">
              {meetings.map((meeting) => (
                <Link
                  key={meeting.id}
                  href={`/meetings/${meeting.id}`}
                  className="flex items-center justify-between rounded-lg border border-border p-3 transition-colors hover:bg-accent"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {meeting.title || `Meeting ${meeting.id}`}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {formatDate(meeting.started_at)} &middot;{" "}
                      {formatDuration(meeting.duration_seconds)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {meeting.has_summary && (
                      <Badge variant="default" className="text-xs">
                        Zusammenfassung
                      </Badge>
                    )}
                    <StatusBadge status={meeting.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatsCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: string;
  value: string;
  icon: React.ElementType;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
              {title}
            </p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          </div>
          <Icon className="h-8 w-8 text-primary opacity-50" />
        </div>
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: Meeting["status"] }) {
  const variants: Record<string, "default" | "secondary" | "destructive"> = {
    recording: "destructive",
    completed: "default",
    failed: "destructive",
  };
  const labels: Record<string, string> = {
    recording: "Aufnahme",
    transcribing: "Transkription",
    summarizing: "Zusammenfassung",
    completed: "Fertig",
    failed: "Fehler",
  };

  return (
    <Badge variant={variants[status] || "secondary"} className="text-xs font-mono">
      {labels[status] || status}
    </Badge>
  );
}
