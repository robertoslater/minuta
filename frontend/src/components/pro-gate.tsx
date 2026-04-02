"use client";

import { useState } from "react";
import { Crown, Lock } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

/**
 * Wraps a Pro feature button. If not Pro, shows upgrade dialog instead.
 */
export function ProGate({
  children,
  feature,
}: {
  children: React.ReactNode;
  feature: string;
}) {
  const { isPro } = useAppStore();

  if (isPro) {
    return <>{children}</>;
  }

  return (
    <UpgradeDialog feature={feature}>
      {children}
    </UpgradeDialog>
  );
}

/**
 * Badge that shows "Pro" or "Free" plan.
 */
export function PlanBadge() {
  const { isPro, plan } = useAppStore();

  return (
    <Badge
      variant={isPro ? "default" : "secondary"}
      className="font-mono text-xs gap-1"
    >
      {isPro && <Crown className="h-3 w-3" />}
      {plan}
    </Badge>
  );
}

/**
 * Pro feature overlay for disabled buttons.
 */
export function ProButton({
  children,
  feature,
  onClick,
  ...props
}: {
  children: React.ReactNode;
  feature: string;
  onClick?: () => void;
} & React.ComponentProps<typeof Button>) {
  const { isPro } = useAppStore();

  if (isPro) {
    return (
      <Button onClick={onClick} {...props}>
        {children}
      </Button>
    );
  }

  return (
    <UpgradeDialog feature={feature}>
      <Button variant="outline" {...props} className={`${props.className || ""} gap-2 opacity-75`}>
        <Lock className="h-3.5 w-3.5" />
        {children}
        <Badge variant="secondary" className="text-[10px] font-mono ml-1">PRO</Badge>
      </Button>
    </UpgradeDialog>
  );
}

function UpgradeDialog({
  children,
  feature,
}: {
  children: React.ReactNode;
  feature: string;
}) {
  const [open, setOpen] = useState(false);
  const [licenseKey, setLicenseKey] = useState("");
  const [activating, setActivating] = useState(false);
  const { setLicense } = useAppStore();

  const handleActivate = async () => {
    if (!licenseKey.trim()) return;
    setActivating(true);
    try {
      const result = await api.activateLicense(licenseKey.trim());
      if (result.status === "activated") {
        setLicense(true, result.plan);
        setOpen(false);
        toast.success("Pro aktiviert!");
      }
    } catch {
      toast.error("Ungültiger License Key");
    } finally {
      setActivating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <div className="cursor-pointer">{children}</div>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-primary" />
            Upgrade auf Pro
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <p className="text-sm text-muted-foreground">
            <strong>{feature}</strong> ist ein Pro-Feature.
            Upgrade auf Minuta Pro für Webhook, Export und Auto-Zusammenfassung.
          </p>

          <Card>
            <CardContent className="pt-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Minuta Pro</span>
                <span className="text-lg font-bold text-primary">CHF 9<span className="text-xs text-muted-foreground font-normal">/Monat</span></span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>CHF 99<span className="text-[10px]">/Jahr</span></span>
                <span className="text-muted-foreground/50">|</span>
                <span>CHF 199 <span className="text-[10px]">einmalig</span></span>
              </div>
              <div className="bg-primary/10 text-primary text-[11px] font-medium px-2 py-1 rounded text-center">
                Early Bird Lifetime: CHF 149 (erste 100 Kaeufe)
              </div>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>&#10003; Webhook / N8N Integration</li>
                <li>&#10003; Notion & Neo4J Export</li>
                <li>&#10003; Auto-Zusammenfassung</li>
                <li>&#10003; CSV / PDF Export</li>
                <li>&#10003; Priority Support</li>
              </ul>
            </CardContent>
          </Card>

          <div className="space-y-2">
            <Input
              placeholder="License Key eingeben"
              value={licenseKey}
              onChange={(e) => setLicenseKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleActivate()}
              className="font-mono text-sm"
            />
            <div className="flex gap-2">
              <Button onClick={handleActivate} disabled={activating || !licenseKey.trim()} className="flex-1">
                {activating ? "Aktiviere..." : "Aktivieren"}
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => window.open("https://morovision.ch/minuta", "_blank")}
              >
                Kaufen &rarr;
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
