'use client';

import { useEffect, useState } from 'react';
import { BuildProgress } from '@/types/models';
import { useWebSocket } from '@/lib/websocket';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Terminal, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useQuery } from '@tanstack/react-query';

interface BuildMonitorProps {
  buildId: string;
  onComplete?: () => void;
}

export function BuildMonitor({ buildId, onComplete }: BuildMonitorProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [progress, setProgress] = useState<BuildProgress | null>(null);
  
  // Fetch build details
  const { data: build, refetch } = useQuery({
    queryKey: ['build', buildId],
    queryFn: () => apiClient.builds.get(buildId),
    refetchInterval: (query) => {
      // Stop refetching when build is complete
      const build = query.state.data;
      return build?.build_status === 'success' || build?.build_status === 'failed' ? false : 2000;
    },
  });

  // WebSocket connection for real-time updates
  const { messages, isConnected } = useWebSocket(buildId);

  useEffect(() => {
    messages.forEach((message) => {
      if (message.type === 'progress') {
        setProgress(message.data as BuildProgress);
      } else if (message.type === 'status') {
        const statusData = message.data as { logs?: string };
        if (statusData.logs) {
          setLogs((prev) => [...prev, statusData.logs!]);
        }
      } else if (message.type === 'complete' || message.type === 'error') {
        refetch();
        if (onComplete) {
          onComplete();
        }
      }
    });
  }, [messages, refetch, onComplete]);

  // Fetch initial logs
  useEffect(() => {
    if (build?.build_logs) {
      setLogs(build.build_logs.split('\n'));
    }
  }, [build?.build_logs]);

  const getStatusIcon = () => {
    switch (build?.build_status) {
      case 'success':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'building':
        return <RefreshCw className="h-5 w-5 animate-spin text-blue-500" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    switch (build?.build_status) {
      case 'success':
        return 'default';
      case 'failed':
        return 'destructive';
      case 'building':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Terminal className="h-5 w-5" />
            <div>
              <CardTitle>Build Monitor</CardTitle>
              <CardDescription>
                {build?.image_name}:{build?.tag}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <Badge variant={getStatusColor() as 'default' | 'destructive' | 'secondary' | 'outline'}>
              {build?.build_status || 'Unknown'}
            </Badge>
            {isConnected && (
              <Badge variant="outline" className="text-green-600">
                Live
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress Bar */}
        {progress && build?.build_status === 'building' && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>{progress.step}</span>
              <span>{progress.progress}/{progress.total}</span>
            </div>
            <Progress value={(progress.progress / progress.total) * 100} />
            <p className="text-sm text-muted-foreground">{progress.message}</p>
          </div>
        )}

        {/* Build Info */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Started</p>
            <p className="font-medium">
              {build?.created_at ? new Date(build.created_at).toLocaleTimeString() : '-'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Duration</p>
            <p className="font-medium">
              {build?.build_duration ? `${Math.round(build.build_duration)}s` : '-'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Image Size</p>
            <p className="font-medium">
              {build?.image_size ? `${(build.image_size / 1024 / 1024 / 1024).toFixed(2)} GB` : '-'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Registry</p>
            <p className="font-medium">
              {build?.registry_url || 'Local'}
            </p>
          </div>
        </div>

        {/* Build Logs */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">Build Logs</h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
          <ScrollArea className="h-[300px] w-full rounded-md border bg-black p-4">
            <pre className="text-xs text-green-400 font-mono">
              {logs.length > 0 ? logs.join('\n') : 'Waiting for logs...'}
            </pre>
          </ScrollArea>
        </div>

        {/* Actions */}
        {build?.build_status === 'success' && (
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1">
              Push to Registry
            </Button>
            <Button className="flex-1">
              Deploy Container
            </Button>
          </div>
        )}

        {build?.build_status === 'failed' && (
          <Button variant="destructive" className="w-full">
            Retry Build
          </Button>
        )}
      </CardContent>
    </Card>
  );
}