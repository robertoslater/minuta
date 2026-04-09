"use client";

import { useEffect, useState } from "react";
import { Crown } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api, type LLMProvider, type LicenseStatus } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function SettingsPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [license, setLicenseState] = useState<LicenseStatus | null>(null);
  const [licenseKey, setLicenseKey] = useState("");
  const [activating, setActivating] = useState(false);
  const { backendConnected, setLicense } = useAppStore();

  useEffect(() => {
    if (!backendConnected) return;
    Promise.all([api.getConfig(), api.getLLMProviders(), api.getLicense()])
      .then(([c, p, l]) => {
        setConfig(c);
        setProviders(p);
        setLicenseState(l);
      })
      .catch(() => toast.error("Einstellungen konnten nicht geladen werden"));
  }, [backendConnected]);

  const handleActivate = async () => {
    if (!licenseKey.trim()) return;
    setActivating(true);
    try {
      const result = await api.activateLicense(licenseKey.trim());
      if (result.status === "activated") {
        setLicense(true, result.plan);
        const l = await api.getLicense();
        setLicenseState(l);
        setLicenseKey("");
        toast.success("Pro aktiviert!");
      }
    } catch {
      toast.error("Ungültiger License Key");
    } finally {
      setActivating(false);
    }
  };

  const handleDeactivate = async () => {
    await api.deactivateLicense();
    setLicense(false, "Free");
    const l = await api.getLicense();
    setLicenseState(l);
    toast.success("Lizenz deaktiviert");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Einstellungen</h1>
        <p className="text-muted-foreground text-sm">
          Konfiguration, LLM-Provider und Lizenz
        </p>
      </div>

      {/* License */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Crown className="h-5 w-5 text-primary" />
            Lizenz
          </CardTitle>
        </CardHeader>
        <CardContent>
          {license && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{license.plan} Plan</p>
                  {license.license_key && (
                    <p className="text-xs text-muted-foreground font-mono mt-1">
                      Key: {license.license_key}
                    </p>
                  )}
                </div>
                <Badge variant={license.is_pro ? "default" : "secondary"} className="text-sm">
                  {license.is_pro ? "Pro" : "Free"}
                </Badge>
              </div>

              {!license.is_pro ? (
                <div className="flex gap-2">
                  <Input
                    placeholder="License Key eingeben"
                    value={licenseKey}
                    onChange={(e) => setLicenseKey(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleActivate()}
                    className="font-mono text-sm"
                  />
                  <Button onClick={handleActivate} disabled={activating || !licenseKey.trim()}>
                    {activating ? "..." : "Aktivieren"}
                  </Button>
                </div>
              ) : (
                <Button variant="outline" size="sm" onClick={handleDeactivate}>
                  Lizenz deaktivieren
                </Button>
              )}

              {!license.is_pro && (
                <div className="text-xs text-muted-foreground space-y-1">
                  <p className="font-medium">Pro Features:</p>
                  {license.pro_features.map((f) => (
                    <p key={f}>&#x2022; {f.replace(/_/g, " ")}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* LLM Providers */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">LLM Provider</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {providers.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between rounded-lg border border-border p-4"
              >
                <div>
                  <p className="font-medium text-sm">{p.name}</p>
                  <p className="text-xs text-muted-foreground font-mono mt-1">
                    Modell: {p.model}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {p.is_default && (
                    <Badge variant="default" className="text-xs">
                      Standard
                    </Badge>
                  )}
                  <Badge
                    variant={p.configured ? "default" : "secondary"}
                    className="text-xs font-mono"
                  >
                    {p.configured ? "Konfiguriert" : "Nicht konfiguriert"}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Config Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Konfiguration</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Bearbeite die Konfiguration direkt in{" "}
            <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
              ~/.minuta/config.toml
            </code>
          </p>
          {config && (
            <pre className="text-xs font-mono bg-muted p-4 rounded-lg overflow-auto max-h-[400px]">
              {JSON.stringify(config, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
