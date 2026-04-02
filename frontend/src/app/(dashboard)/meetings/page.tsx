"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Clock, FileText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, type Meeting } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { formatDuration, formatDate } from "@/lib/format";

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const { backendConnected } = useAppStore();

  const loadMeetings = async () => {
    try {
      const data = await api.listMeetings({ limit: 100 });
      setMeetings(data);
    } catch {
      // Backend not available
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (backendConnected) loadMeetings();
  }, [backendConnected]);

  const deleteMeeting = async (id: string) => {
    try {
      await api.deleteMeeting(id);
      setMeetings((prev) => prev.filter((m) => m.id !== id));
      toast.success("Meeting geloescht");
    } catch {
      toast.error("Fehler beim Loeschen");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Meetings</h1>
        <p className="text-muted-foreground text-sm">
          Alle aufgezeichneten Meetings
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Laden...</p>
      ) : meetings.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <Clock className="mx-auto h-12 w-12 text-muted-foreground opacity-50" />
            <p className="mt-4 text-sm text-muted-foreground">
              Noch keine Meetings vorhanden.
            </p>
            <Link href="/record" className={buttonVariants({ className: "mt-4" })}>
              Erste Aufnahme starten
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {meetings.map((meeting) => (
            <Card key={meeting.id} className="transition-colors hover:border-primary/50">
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <Link href={`/meetings/${meeting.id}`} className="flex-1">
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="font-medium">
                          {meeting.title || `Meeting ${meeting.id}`}
                        </p>
                        <p className="text-xs text-muted-foreground font-mono mt-1">
                          {formatDate(meeting.started_at)} &middot;{" "}
                          {formatDuration(meeting.duration_seconds)} &middot;{" "}
                          {meeting.transcript_segment_count} Segmente
                        </p>
                      </div>
                    </div>
                  </Link>
                  <div className="flex items-center gap-2">
                    {meeting.has_summary && (
                      <Badge variant="default" className="text-xs">
                        <FileText className="mr-1 h-3 w-3" />
                        Zusammenfassung
                      </Badge>
                    )}
                    {meeting.webhook_sent && (
                      <Badge variant="secondary" className="text-xs font-mono">
                        Webhook
                      </Badge>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.preventDefault();
                        deleteMeeting(meeting.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
