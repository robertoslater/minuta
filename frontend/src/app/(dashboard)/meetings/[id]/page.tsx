"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  Send,
  Pencil,
  Check,
  X,
  Clock,
  MessageSquare,
  Building2,
  FolderKanban,
  Globe,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ProButton } from "@/components/pro-gate";
import {
  api,
  type Meeting,
  type TranscriptSegment,
  type Summary,
} from "@/lib/api";
import { formatDuration, formatDate, formatTime } from "@/lib/format";

export default function MeetingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const meetingId = params.id as string;

  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [summarizing, setSummarizing] = useState(false);
  const [webhookSent, setWebhookSent] = useState(false);
  const [sendingWebhook, setSendingWebhook] = useState(false);

  // Edit states
  const [editingTitle, setEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editingSummary, setEditingSummary] = useState(false);
  const [editSummaryTitle, setEditSummaryTitle] = useState("");
  const [editKeyPoints, setEditKeyPoints] = useState("");
  const [editActionItems, setEditActionItems] = useState("");
  const [editDecisions, setEditDecisions] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [m, t] = await Promise.all([
          api.getMeeting(meetingId),
          api.getTranscript(meetingId),
        ]);
        setMeeting(m);
        setTranscript(t);

        if (m.has_summary) {
          try {
            const s = await api.getSummary(meetingId);
            setSummary(s);
          } catch {}
        }
      } catch {
        toast.error("Meeting nicht gefunden");
        router.push("/meetings");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [meetingId, router]);

  const handleSummarize = async () => {
    setSummarizing(true);
    try {
      const s = await api.summarizeMeeting(meetingId);
      setSummary(s);
      toast.success("Zusammenfassung erstellt");
    } catch {
      toast.error("Zusammenfassung fehlgeschlagen");
    } finally {
      setSummarizing(false);
    }
  };

  const handleWebhook = async () => {
    setSendingWebhook(true);
    try {
      await api.sendWebhook(meetingId);
      setWebhookSent(true);
      toast.success("Webhook gesendet");
    } catch {
      toast.error("Webhook fehlgeschlagen");
      setSendingWebhook(false);
    }
  };

  // Title editing
  const startEditTitle = () => {
    setEditTitle(meeting?.title || "");
    setEditingTitle(true);
  };
  const saveTitle = async () => {
    try {
      const updated = await api.updateMeeting(meetingId, { title: editTitle });
      setMeeting(updated);
      setEditingTitle(false);
      toast.success("Titel gespeichert");
    } catch {
      toast.error("Fehler beim Speichern");
    }
  };

  // Summary editing
  const startEditSummary = () => {
    if (!summary) return;
    setEditSummaryTitle(summary.title);
    setEditKeyPoints(summary.key_points.join("\n"));
    setEditActionItems(summary.action_items.join("\n"));
    setEditDecisions(summary.decisions.join("\n"));
    setEditingSummary(true);
  };
  const saveSummary = async () => {
    try {
      const updated = await api.updateSummary(meetingId, {
        title: editSummaryTitle,
        key_points: editKeyPoints.split("\n").filter((l) => l.trim()),
        action_items: editActionItems.split("\n").filter((l) => l.trim()),
        decisions: editDecisions.split("\n").filter((l) => l.trim()),
      });
      setSummary(updated);
      setEditingSummary(false);
      toast.success("Zusammenfassung gespeichert");
    } catch {
      toast.error("Fehler beim Speichern");
    }
  };

  if (loading) return <p className="text-sm text-muted-foreground">Laden...</p>;
  if (!meeting) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/meetings")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          {editingTitle ? (
            <div className="flex items-center gap-2">
              <Input
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="text-xl font-bold h-10"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && saveTitle()}
              />
              <Button size="sm" onClick={saveTitle}>
                <Check className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingTitle(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2 group">
              <h1 className="text-2xl font-bold tracking-tight">
                {meeting.title || `Meeting ${meeting.id}`}
              </h1>
              <Button
                variant="ghost"
                size="sm"
                className="opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={startEditTitle}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
          <p className="text-sm text-muted-foreground font-mono">
            {formatDate(meeting.started_at)} &middot;{" "}
            {formatDuration(meeting.duration_seconds)} &middot;{" "}
            {meeting.transcript_segment_count} Segmente
          </p>
        </div>
        <div className="flex gap-2">
          {!meeting.has_summary && (
            <Button onClick={handleSummarize} disabled={summarizing} className="gap-2">
              <FileText className="h-4 w-4" />
              {summarizing ? "Generiere..." : "Zusammenfassen"}
            </Button>
          )}
          <ProButton
            feature="Webhook / N8N Integration"
            variant="outline"
            onClick={handleWebhook}
            disabled={webhookSent || sendingWebhook || meeting.webhook_sent}
            className="gap-2"
          >
            <Send className="h-4 w-4" />
            {meeting.webhook_sent || webhookSent ? "Gesendet" : sendingWebhook ? "Sende..." : "Webhook"}
          </ProButton>
        </div>
      </div>

      {/* Meta Fields */}
      <MetaFields meeting={meeting} onUpdate={setMeeting} meetingId={meetingId} />

      {/* Tabs */}
      <Tabs defaultValue={summary ? "summary" : "transcript"}>
        <TabsList>
          <TabsTrigger value="transcript" className="gap-1.5">
            <MessageSquare className="h-3.5 w-3.5" />
            Transkript
          </TabsTrigger>
          <TabsTrigger value="summary" className="gap-1.5" disabled={!summary}>
            <FileText className="h-3.5 w-3.5" />
            Zusammenfassung
          </TabsTrigger>
        </TabsList>

        {/* Transcript Tab */}
        <TabsContent value="transcript">
          <Card>
            <CardContent className="pt-6">
              <ScrollArea className="h-[500px]">
                {transcript.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    Kein Transkript vorhanden.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {transcript.map((seg) => (
                      <div key={seg.id} className="flex gap-3">
                        <div className="flex-shrink-0 w-16 text-right">
                          <span className="text-xs text-muted-foreground font-mono">
                            {formatTime(seg.start_time)}
                          </span>
                        </div>
                        <Badge
                          variant={seg.source === "mic" ? "default" : "secondary"}
                          className="text-xs font-mono flex-shrink-0"
                        >
                          {seg.speaker}
                        </Badge>
                        <p className="text-sm leading-relaxed flex-1">{seg.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Summary Tab */}
        <TabsContent value="summary">
          {summary && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>{summary.title}</CardTitle>
                      <p className="text-xs text-muted-foreground font-mono mt-1">
                        {summary.provider} / {summary.model} &middot;{" "}
                        {summary.generation_time_seconds}s &middot;{" "}
                        {summary.token_count} Tokens
                      </p>
                    </div>
                    {!editingSummary && (
                      <Button variant="ghost" size="sm" onClick={startEditSummary}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {editingSummary ? (
                    /* Edit Mode */
                    <div className="space-y-4">
                      <div>
                        <label className="text-sm font-semibold mb-1 block">Titel</label>
                        <Input
                          value={editSummaryTitle}
                          onChange={(e) => setEditSummaryTitle(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="text-sm font-semibold mb-1 block">
                          Hauptpunkte <span className="text-muted-foreground font-normal">(ein Punkt pro Zeile)</span>
                        </label>
                        <Textarea
                          value={editKeyPoints}
                          onChange={(e) => setEditKeyPoints(e.target.value)}
                          rows={4}
                        />
                      </div>
                      <div>
                        <label className="text-sm font-semibold mb-1 block">
                          Action Items <span className="text-muted-foreground font-normal">(ein Item pro Zeile)</span>
                        </label>
                        <Textarea
                          value={editActionItems}
                          onChange={(e) => setEditActionItems(e.target.value)}
                          rows={4}
                        />
                      </div>
                      <div>
                        <label className="text-sm font-semibold mb-1 block">
                          Entscheidungen <span className="text-muted-foreground font-normal">(eine pro Zeile)</span>
                        </label>
                        <Textarea
                          value={editDecisions}
                          onChange={(e) => setEditDecisions(e.target.value)}
                          rows={4}
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={saveSummary} className="gap-2">
                          <Check className="h-4 w-4" />
                          Speichern
                        </Button>
                        <Button variant="ghost" onClick={() => setEditingSummary(false)}>
                          Abbrechen
                        </Button>
                      </div>
                    </div>
                  ) : (
                    /* View Mode */
                    <>
                      {summary.key_points.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-2">Hauptpunkte</h3>
                          <ul className="list-disc list-inside space-y-1 text-sm">
                            {summary.key_points.map((p, i) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {summary.action_items.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-2">Action Items</h3>
                          <ul className="space-y-1 text-sm">
                            {summary.action_items.map((a, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <input type="checkbox" className="mt-1 accent-primary" />
                                <span>{a}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {summary.decisions.length > 0 && (
                        <div>
                          <h3 className="text-sm font-semibold mb-2">Entscheidungen</h3>
                          <ul className="list-disc list-inside space-y-1 text-sm">
                            {summary.decisions.map((d, i) => (
                              <li key={i}>{d}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {summary.sections.map((sec, i) => (
                        <div key={i}>
                          <h3 className="text-sm font-semibold mb-2">{sec.heading}</h3>
                          <p className="text-sm text-muted-foreground">{sec.content}</p>
                        </div>
                      ))}
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MetaFields({
  meeting,
  meetingId,
  onUpdate,
}: {
  meeting: Meeting;
  meetingId: string;
  onUpdate: (m: Meeting) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [company, setCompany] = useState(meeting.company || "");
  const [project, setProject] = useState(meeting.project || "");
  const [domain, setDomain] = useState(meeting.domain || "");

  const save = async () => {
    try {
      const updated = await api.updateMeeting(meetingId, { company, project, domain });
      onUpdate(updated);
      setEditing(false);
      toast.success("Gespeichert");
    } catch {
      toast.error("Fehler beim Speichern");
    }
  };

  if (editing) {
    return (
      <Card>
        <CardContent className="pt-5 pb-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5">
                <Building2 className="h-3.5 w-3.5" /> Unternehmen
              </label>
              <Input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Firmenname" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5">
                <FolderKanban className="h-3.5 w-3.5" /> Projekt
              </label>
              <Input value={project} onChange={(e) => setProject(e.target.value)} placeholder="Projektname" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5">
                <Globe className="h-3.5 w-3.5" /> Domain
              </label>
              <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="example.com" />
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <Button size="sm" onClick={save} className="gap-1.5">
              <Check className="h-3.5 w-3.5" /> Speichern
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Abbrechen
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const hasData = meeting.company || meeting.project || meeting.domain;

  return (
    <Card className="group">
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center justify-between">
          <div className="grid grid-cols-3 gap-6 flex-1">
            <div className="flex items-center gap-2 text-sm">
              <Building2 className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Unternehmen:</span>
              <span className="font-medium">{meeting.company || "–"}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <FolderKanban className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Projekt:</span>
              <span className="font-medium">{meeting.project || "–"}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Domain:</span>
              <span className="font-medium">{meeting.domain || "–"}</span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={() => {
              setCompany(meeting.company || "");
              setProject(meeting.project || "");
              setDomain(meeting.domain || "");
              setEditing(true);
            }}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
