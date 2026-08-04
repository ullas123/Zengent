/**
 * Developer      : Ullas Krishnan
 * Designation    : Sr Solution Architect
 * Organisation   : Zensar Technologies
 * Developed by   : Zensar Diamond Team
 * Date           : 29 July 2026
 */

import { storage } from "../storage";
import { insertProjectSchema, type GithubProject } from "@shared/schema";
import { analyzeJavaProject } from "./javaAnalyzer";
import { analyzeCobolProject } from "./cobolAnalyzer";
import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const execAsync = promisify(exec);

export async function analyzeGithubRepository(githubData: GithubProject): Promise<string> {
  let tempDir: string | null = null;
  
  try {
    // Parse GitHub URL to extract owner/repo
    const githubUrl = githubData.githubUrl;
    const urlMatch = githubUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    
    if (!urlMatch) {
      throw new Error('Invalid GitHub URL format');
    }
    
    const [, owner, repoName] = urlMatch;
    const cleanRepoName = repoName.replace('.git', '');
    const githubRepo = `${owner}/${cleanRepoName}`;
    
    // Create project record
    const projectData = {
      name: githubData.name || cleanRepoName,
      githubUrl: githubUrl,
      githubRepo: githubRepo,
      githubBranch: githubData.githubBranch,
      sourceType: 'github' as const,
      status: 'processing' as const,
      originalFileName: null,
      analysisData: null,
      fileCount: 0,
      controllerCount: 0,
      serviceCount: 0,
      repositoryCount: 0,
      entityCount: 0,
    };

    const validatedData = insertProjectSchema.parse(projectData);
    const project = await storage.createProject(validatedData);

    // Clone repository in background
    cloneAndAnalyzeRepository(project.id, githubUrl, githubData.githubBranch).catch((error) => {
      console.error(`GitHub analysis failed for project ${project.id}:`, error);
      storage.updateProject(project.id, { 
        status: 'failed',
      });
    });

    return project.id;
  } catch (error) {
    console.error('GitHub analysis error:', error);
    throw error;
  }
}

async function cloneAndAnalyzeRepository(projectId: string, githubUrl: string, branch: string = 'main'): Promise<void> {
  let tempDir: string | null = null;
  
  try {
    // Create temporary directory
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'github-analyzer-'));
    
    // Clone repository with fallback branch logic
    const cloneUrl = githubUrl.endsWith('.git') ? githubUrl : `${githubUrl}.git`;
    
    try {
      // Try with specified branch first
      await execAsync(`git clone --depth 1 --branch ${branch} ${cloneUrl} ${tempDir}/repo`, {
        timeout: 60000, // 1 minute timeout
      });
    } catch (branchError) {
      console.log(`Branch ${branch} not found, trying to clone without branch specification`);
      
      // If branch doesn't exist, clone without branch specification and use default
      await execAsync(`git clone --depth 1 ${cloneUrl} ${tempDir}/repo`, {
        timeout: 60000,
      });
      
      // Get the actual default branch
      const { stdout: branchOutput } = await execAsync(`cd ${tempDir}/repo && git branch --show-current`);
      const actualBranch = branchOutput.trim();
      console.log(`Using default branch: ${actualBranch}`);
      
      // Update project with actual branch used
      await storage.updateProject(projectId, { githubBranch: actualBranch });
    }
    
    const repoPath = path.join(tempDir, 'repo');
    
    // Find all source files recursively
    const javaFiles = await findJavaFiles(repoPath);
    const cobolFiles = await findCobolFiles(repoPath);
    
    // Determine project type based on files found
    const isCobolProject = cobolFiles.length > 0;
    const isJavaProject = javaFiles.length > 0;
    
    if (!isCobolProject && !isJavaProject) {
      console.log('No Java or COBOL files found in repository');
      await storage.updateProject(projectId, {
        status: 'failed',
      });
      return;
    }

    if (isCobolProject) {
      console.log(`Detected COBOL/Mainframe project with ${cobolFiles.length} files`);
      // Create a ZIP buffer with all COBOL-related files
      const zipBuffer = await createAnalysisBuffer(cobolFiles, repoPath);
      await analyzeCobolProject(projectId, zipBuffer);
    } else {
      console.log(`Detected Java project with ${javaFiles.length} files`);
      // Create a ZIP buffer for Java files
      const zipBuffer = await createAnalysisBuffer(javaFiles, repoPath);
      await analyzeJavaProject(projectId, zipBuffer);
    }

  } catch (error) {
    console.error('Repository analysis error:', error);
    await storage.updateProject(projectId, {
      status: 'failed',
    });
  } finally {
    // Clean up temporary directory
    if (tempDir && fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  }
}

async function findJavaFiles(dirPath: string): Promise<string[]> {
  const javaFiles: string[] = [];
  
  function traverseDirectory(currentPath: string) {
    const items = fs.readdirSync(currentPath);
    
    for (const item of items) {
      const itemPath = path.join(currentPath, item);
      const stat = fs.statSync(itemPath);
      
      if (stat.isDirectory()) {
        // Skip common non-source directories
        if (!['node_modules', '.git', 'target', 'build', '.gradle', '.idea', '.vscode'].includes(item)) {
          traverseDirectory(itemPath);
        }
      } else if (item.endsWith('.java')) {
        javaFiles.push(itemPath);
      }
    }
  }
  
  traverseDirectory(dirPath);
  return javaFiles;
}

async function findCobolFiles(dirPath: string): Promise<string[]> {
  const cobolFiles: string[] = [];
  const cobolExtensions = ['.cbl', '.cob', '.cobol', '.jcl', '.cpy', '.copy', '.proc'];
  
  function traverseDirectory(currentPath: string) {
    const items = fs.readdirSync(currentPath);
    
    for (const item of items) {
      const itemPath = path.join(currentPath, item);
      const stat = fs.statSync(itemPath);
      
      if (stat.isDirectory()) {
        // Skip common non-source directories
        if (!['node_modules', '.git', 'target', 'build', '.gradle', '.idea', '.vscode'].includes(item)) {
          traverseDirectory(itemPath);
        }
      } else {
        const lowerItem = item.toLowerCase();
        if (cobolExtensions.some(ext => lowerItem.endsWith(ext))) {
          cobolFiles.push(itemPath);
        }
      }
    }
  }
  
  traverseDirectory(dirPath);
  return cobolFiles;
}

async function createAnalysisBuffer(sourceFiles: string[], basePath: string): Promise<Buffer> {
  // Create a simple archive format for the analyzer
  const JSZip = (await import('jszip')).default;
  const zip = new JSZip();
  
  for (const filePath of sourceFiles) {
    const relativePath = path.relative(basePath, filePath);
    const content = fs.readFileSync(filePath);
    zip.file(relativePath, content);
  }
  
  return await zip.generateAsync({ type: 'nodebuffer' });
}

export function isValidGithubUrl(url: string): boolean {
  // Accepts public GitHub (github.com) and enterprise GitHub (e.g. github.aexp.com)
  const githubUrlPattern = /^https:\/\/github[^\/]*\/[^\/]+\/[^\/]+(\.git)?\/?$/;
  return githubUrlPattern.test(url);
}

export function extractRepoInfo(githubUrl: string): { owner: string; repo: string } | null {
  const match = githubUrl.match(/github\.com\/([^\/]+)\/([^\/]+)/);
  if (!match) return null;
  
  const [, owner, repo] = match;
  return { owner, repo: repo.replace('.git', '') };
}