"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";
import { type Hook, type Plugin, pluginsApi } from "@/lib/plugins-api";

/**
 * Installed plugins, what each one is allowed to do, and which hooks they are
 * attached to.
 *
 * Read-only by design: installing a plugin loads third-party code into the
 * server process, which is a deployment action. Exposing it as a button would
 * turn any account takeover into remote code execution.
 */
export default function PluginsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const [p, h] = await Promise.all([
          pluginsApi.list(token),
          pluginsApi.hooks(token),
        ]);
        if (cancelled) return;
        setPlugins(p);
        setHooks(h);
      } catch (err) {
        if (!cancelled) {
          toast.error(
            err instanceof ApiRequestError ? err.message : "Failed to load plugins.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Plugins</h1>
        <Badge variant="secondary">{plugins.length} installed</Badge>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {plugins.map((plugin) => (
              <Card key={plugin.name}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2">
                    <span>{plugin.display_name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      v{plugin.version}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-muted-foreground">{plugin.description}</p>

                  <div className="flex flex-wrap gap-1">
                    {plugin.hooks.map((hook) => (
                      <Badge key={hook} variant="outline">
                        {hook}
                      </Badge>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-1">
                    {plugin.granted_capabilities.map((cap) => (
                      <Badge key={cap} variant="success">
                        {cap}
                      </Badge>
                    ))}
                    {/* Refused capabilities are shown, not hidden: a plugin
                        that asked for the network and did not get it explains
                        why it is not doing what its README claims. */}
                    {plugin.refused_capabilities.map((cap) => (
                      <Badge key={cap} variant="destructive">
                        {cap} refused
                      </Badge>
                    ))}
                  </div>

                  <p className="text-xs text-muted-foreground">
                    priority {plugin.priority} · timeout {plugin.timeout_seconds}s
                    {plugin.author && ` · by ${plugin.author}`}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Hooks</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-4 font-medium">Hook</th>
                      <th className="py-2 font-medium">Plugins, in order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hooks.map((hook) => (
                      <tr key={hook.hook} className="border-t">
                        <td className="py-2 pr-4 font-mono text-xs">{hook.hook}</td>
                        <td className="py-2">
                          {hook.plugins.length === 0 ? (
                            <span className="text-muted-foreground">none</span>
                          ) : (
                            hook.plugins.join(" → ")
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
