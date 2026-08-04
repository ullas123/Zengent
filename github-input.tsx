/**
 * Developer      : Ullas Krishnan
 * Designation    : Sr Solution Architect
 * Organisation   : Zensar Technologies
 * Developed by   : Zensar Diamond Team
 * Date           : 29 July 2026
 */

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { type Project, type GithubProject } from "@shared/schema";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Github, GitBranch, Link, ExternalLink } from "lucide-react";

interface GithubInputProps {
  onRepoAnalyzed: (project: Project) => void;
  projectType?: string;
}

export default function GithubInput({ onRepoAnalyzed, projectType }: GithubInputProps) {
  const getDefaultUrl = () => {
    switch (projectType) {
      case 'mainframe':
        return 'https://github.com/aws-samples/aws-mainframe-modernization-carddemo';
      case 'java':
      default:
        return 'https://github.com/kartik1502/Spring-Boot-Microservices-Banking-Application';
    }
  };

  const [githubUrl, setGithubUrl] = useState(getDefaultUrl());
  const [projectName, setProjectName] = useState("");
  const [branch, setBranch] = useState("main");
  const { toast } = useToast();

  const getProjectTypeLabel = () => {
    switch (projectType) {
      case 'mainframe':
        return 'COBOL/Mainframe';
      case 'python':
        return 'Python';
      case 'pyspark':
        return 'PySpark';
      case 'csharp':
        return 'C#/.NET';
      case 'kotlin':
        return 'Kotlin';
      case 'java':
      default:
        return 'Java';
    }
  };

  const getExampleRepos = () => {
    switch (projectType) {
      case 'mainframe':
        return [
          'https://github.com/writ3it/cobol-examples',
          'https://github.com/aws-samples/aws-mainframe-modernization-carddemo',
        ];
      case 'python':
        return [
          'https://github.com/django/django',
          'https://github.com/pallets/flask',
        ];
      case 'pyspark':
        return [
          'https://github.com/apache/spark',
          'https://github.com/username/pyspark-etl',
        ];
      default:
        return [
          'https://github.com/kartik1502/Spring-Boot-Microservices-Banking-Application',
          'https://github.com/spring-projects/spring-boot',
        ];
    }
  };

  const analyzeGithubMutation = useMutation({
    mutationFn: async (data: GithubProject) => {
      const response = await apiRequest('POST', '/api/projects/github', data);
      return response.json();
    },
    onSuccess: (project: Project) => {
      toast({
        title: "GitHub Repository Analysis Started",
        description: "Your repository is being cloned and analyzed...",
      });
      onRepoAnalyzed(project);
      setGithubUrl("");
      setProjectName("");
      setBranch("main");
    },
    onError: (error: Error) => {
      toast({
        title: "Analysis Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!githubUrl.trim()) {
      toast({
        title: "Missing URL",
        description: "Please enter a GitHub repository URL",
        variant: "destructive",
      });
      return;
    }

    const urlPattern = /^https:\/\/github[^\/]*\/[^\/]+\/[^\/]+(\.git)?\/?$/;
    if (!urlPattern.test(githubUrl.trim())) {
      toast({
        title: "Invalid URL",
        description: "Please enter a valid GitHub repository URL (e.g., https://github.com/user/repo or https://github.aexp.com/user/repo)",
        variant: "destructive",
      });
      return;
    }

    analyzeGithubMutation.mutate({
      githubUrl: githubUrl.trim(),
      name: projectName.trim() || "Untitled Project",
      githubBranch: branch.trim() || "main",
    });
  };

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value;
    setGithubUrl(url);
    
    if (url) {
      const match = url.match(/github\.com\/[^\/]+\/([^\/]+)/);
      if (match) {
        setProjectName(match[1].replace('.git', ''));
      }
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Github className="text-primary w-5 h-5" />
          <span>Analyze GitHub Repository</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="github-url" className="flex items-center space-x-2">
              <Link className="w-4 h-4" />
              <span>GitHub Repository URL</span>
            </Label>
            <Input
              id="github-url"
              type="url"
              placeholder="https://github.com/username/repository"
              value={githubUrl}
              onChange={handleUrlChange}
              disabled={analyzeGithubMutation.isPending}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Enter the public GitHub repository URL containing {getProjectTypeLabel()} source code
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="project-name">Project Name (Optional)</Label>
              <Input
                id="project-name"
                type="text"
                placeholder={`My ${getProjectTypeLabel()} Project`}
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                disabled={analyzeGithubMutation.isPending}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="branch" className="flex items-center space-x-2">
                <GitBranch className="w-4 h-4" />
                <span>Branch</span>
              </Label>
              <Input
                id="branch"
                type="text"
                placeholder="main"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                disabled={analyzeGithubMutation.isPending}
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-4">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <ExternalLink className="w-4 h-4" />
              <span>Repository will be cloned and analyzed</span>
            </div>
            <Button 
              type="submit" 
              disabled={analyzeGithubMutation.isPending || !githubUrl.trim()}
              className="min-w-[120px]"
            >
              {analyzeGithubMutation.isPending ? "Analyzing..." : "Analyze Repository"}
            </Button>
          </div>
        </form>

        <div className="mt-6 p-4 bg-muted rounded-lg">
          <h4 className="text-sm font-medium mb-2">Example {getProjectTypeLabel()} repositories:</h4>
          <div className="space-y-1 text-xs text-muted-foreground">
            {getExampleRepos().map((repo, index) => (
              <div key={index} className="font-mono">{repo}</div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
