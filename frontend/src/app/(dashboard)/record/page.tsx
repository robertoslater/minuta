"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Square, FileText } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { api, createTranscriptWS, type TranscriptSegment } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { formatTime } from "@/lib/format";

export default function RecordPage() {
  const {
    isRecording,
    currentMeetingId,
    setRecording,
    liveSegments,
    addSegment,
    clearSegments,
    backendConnected,
  } = useAppStore();

  const [elapsed, setElapsed] = useState(0);
  const [summarizing, setSummarizing] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  // Auto-scroll transcript
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [liveSegments]);

  // Timer
  useEffect(() => {
    if (isRecording) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording]);

  const startRecording = useCallback(async () => {
    if (!backendConnected) {
      toast.error("Backend nicht verbunden");
      return;
    }
    try {
      clearSegments();
      const meeting = await api.createMeeting({
        title: "",
        audio_source: "mic+system",
      });
      setRecording(true, meeting.id);

      // Connect WebSocket
      const ws = createTranscriptWS(meeting.id);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === "segment") {
          addSegment(data.data as TranscriptSegment);
        }
      };
      ws.onerror = () => toast.error("WebSocket Fehler");
      wsRef.current = ws;

      toast.success("Aufnahme gestartet");
    } catch (err) {
      toast.error("Fehler beim Starten der Aufnahme");
    }
  }, [backendConnected, clearSegments, setRecording, addSegment]);

  const stopRecording = useCallback(async () => {
    if (!currentMeetingId) return;
    try {
      await api.stopMeeting(currentMeetingId);
      wsRef.current?.close();
      setRecording(false);
      toast.success("Aufnahme gestoppt");
    } catch (err) {
      toast.error("Fehler beim Stoppen der Aufnahme");
    }
  }, [currentMeetingId, setRecording]);

  const generateSummary = useCallback(async () => {
    if (!currentMeetingId) return;
    setSummarizing(true);
    try {
      const summary = await api.summarizeMeeting(currentMeetingId);
      toast.success(`Zusammenfassung erstellt: ${summary.title}`);
    } catch (err) {
      toast.error("Zusammenfassung fehlgeschlagen");
    } finally {
      setSummarizing(false);
    }
  }, [currentMeetingId]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Aufnahme</h1>
          <p className="text-muted-foreground text-sm">
            Meeting aufzeichnen und live transkribieren
          </p>
        </div>
        {isRecording && (
          <div className="flex items-center gap-3">
            <Badge variant="destructive" className="animate-pulse gap-1.5 font-mono">
              <span className="h-1.5 w-1.5 rounded-full bg-white" />
              REC {formatTime(elapsed)}
            </Badge>
          </div>
        )}
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center gap-4">
            {!isRecording ? (
              <Button
                size="lg"
                onClick={startRecording}
                disabled={!backendConnected}
                className="gap-2 px-8"
              >
                <Mic className="h-5 w-5" />
                Aufnahme starten
              </Button>
            ) : (
              <>
                <Button
                  size="lg"
                  variant="destructive"
                  onClick={stopRecording}
                  className="gap-2 px-8"
                >
                  <Square className="h-5 w-5" />
                  Aufnahme stoppen
                </Button>
              </>
            )}
            {!isRecording && liveSegments.length > 0 && (
              <Button
                variant="outline"
                onClick={generateSummary}
                disabled={summarizing}
                className="gap-2"
              >
                <FileText className="h-4 w-4" />
                {summarizing ? "Wird erstellt..." : "Zusammenfassung"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Live Transcript */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            Live Transkript
            {isRecording && (
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] rounded-md border border-border p-4" ref={scrollRef}>
            {liveSegments.length === 0 ? (
              <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
                {isRecording
                  ? "Warte auf Sprache..."
                  : "Starte eine Aufnahme, um das Live-Transkript zu sehen."}
              </div>
            ) : (
              <div className="space-y-3">
                {liveSegments.map((seg) => (
                  <div key={seg.id} className="flex gap-3">
                    <div className="flex-shrink-0 pt-0.5">
                      <Badge
                        variant={seg.source === "mic" ? "default" : "secondary"}
                        className="text-xs font-mono"
                      >
                        {seg.speaker}
                      </Badge>
                    </div>
                    <div className="flex-1">
                      <p className="text-sm leading-relaxed">{seg.text}</p>
                      <p className="text-xs text-muted-foreground font-mono mt-0.5">
                        {formatTime(seg.start_time)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}
