'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { WorkflowTable } from './workflow-table';
import { WorkflowUpload } from './workflow-upload';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RefreshCw, Search, Upload } from 'lucide-react';

export function WorkflowDashboard() {
  const [searchTerm, setSearchTerm] = useState('');
  const [showUpload, setShowUpload] = useState(false);

  const { data: workflows, isLoading, error, refetch } = useQuery({
    queryKey: ['workflows', searchTerm],
    queryFn: async () => {
      console.log('Fetching workflows...');
      try {
        const params: any = { limit: 100 };
        if (searchTerm) {
          params.name_filter = searchTerm;
        }
        const result = await apiClient.workflows.list(params);
        console.log('Workflows fetched:', result);
        return result;
      } catch (err) {
        console.error('Error fetching workflows:', err);
        throw err;
      }
    },
  });

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between">
        <div className="flex gap-2 flex-1">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search workflows..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button onClick={() => refetch()} variant="outline" size="icon">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
        <Button onClick={() => setShowUpload(true)}>
          <Upload className="h-4 w-4 mr-2" />
          Upload Workflow
        </Button>
      </div>

      {/* Main Content */}
      <Tabs defaultValue="workflows" className="w-full">
        <TabsList>
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
          <TabsTrigger value="builds">Recent Builds</TabsTrigger>
          <TabsTrigger value="executions">Executions</TabsTrigger>
        </TabsList>

        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Workflows</CardTitle>
              <CardDescription>
                Manage your ComfyUI workflows and generate Docker containers
              </CardDescription>
            </CardHeader>
            <CardContent>
              {console.log('Render state:', { isLoading, error, workflows })}
              {isLoading ? (
                <div className="text-center py-8">Loading workflows...</div>
              ) : error ? (
                <div className="text-center py-8 text-red-500">
                  Error loading workflows: {(error as Error).message}
                </div>
              ) : workflows && workflows.length > 0 ? (
                <WorkflowTable workflows={workflows} />
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No workflows found. Upload your first workflow to get started.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="builds">
          <Card>
            <CardHeader>
              <CardTitle>Recent Builds</CardTitle>
              <CardDescription>
                Monitor your Docker container builds
              </CardDescription>
            </CardHeader>
            <CardContent>
              <BuildsList />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="executions">
          <Card>
            <CardHeader>
              <CardTitle>Workflow Executions</CardTitle>
              <CardDescription>
                Track workflow execution history
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ExecutionsList />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Upload Dialog */}
      {showUpload && (
        <WorkflowUpload
          open={showUpload}
          onClose={() => setShowUpload(false)}
          onSuccess={() => {
            setShowUpload(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}

function BuildsList() {
  const { data: builds, isLoading } = useQuery({
    queryKey: ['builds'],
    queryFn: () => apiClient.builds.list(),
  });

  if (isLoading) return <div>Loading builds...</div>;

  return (
    <div className="space-y-2">
      {builds?.map((build) => (
        <div key={build.id} className="flex items-center justify-between p-4 border rounded-lg">
          <div>
            <p className="font-medium">{build.image_name}:{build.tag}</p>
            <p className="text-sm text-muted-foreground">
              Status: <span className={`font-medium ${
                build.build_status === 'success' ? 'text-green-600' :
                build.build_status === 'failed' ? 'text-red-600' :
                build.build_status === 'building' ? 'text-yellow-600' :
                'text-gray-600'
              }`}>{build.build_status}</span>
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            {new Date(build.created_at).toLocaleDateString()}
          </p>
        </div>
      ))}
    </div>
  );
}

function ExecutionsList() {
  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions'],
    queryFn: () => apiClient.executions.list(),
  });

  if (isLoading) return <div>Loading executions...</div>;

  return (
    <div className="space-y-2">
      {executions?.map((execution) => (
        <div key={execution.id} className="flex items-center justify-between p-4 border rounded-lg">
          <div>
            <p className="font-medium">Prompt: {execution.prompt_id}</p>
            <p className="text-sm text-muted-foreground">
              Status: <span className={`font-medium ${
                execution.status === 'completed' ? 'text-green-600' :
                execution.status === 'failed' ? 'text-red-600' :
                execution.status === 'running' ? 'text-yellow-600' :
                'text-gray-600'
              }`}>{execution.status}</span>
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            {new Date(execution.started_at).toLocaleDateString()}
          </p>
        </div>
      ))}
    </div>
  );
}