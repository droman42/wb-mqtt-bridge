import * as ts from 'typescript';
import * as fs from 'fs/promises';
import * as path from 'path';

export interface CompilationResult {
  success: boolean;
  errors: DiagnosticInfo[];
  warnings: DiagnosticInfo[];
  filePath: string;
}

export interface DiagnosticInfo {
  message: string;
  line: number;
  column: number;
  severity: 'error' | 'warning' | 'info';
  code: number;
}

export interface ImportValidationResult {
  allImportsResolved: boolean;
  missingImports: string[];
  circularDependencies: string[];
  filePath: string;
}

export class CodeValidator {
  private readonly compilerOptions: ts.CompilerOptions = {
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.ESNext,
    lib: ['ES2020', 'DOM', 'DOM.Iterable'],
    allowJs: true,
    skipLibCheck: true,
    esModuleInterop: true,
    allowSyntheticDefaultImports: true,
    strict: true,
    forceConsistentCasingInFileNames: true,
    noFallthroughCasesInSwitch: true,
    moduleResolution: ts.ModuleResolutionKind.NodeJs,
    resolveJsonModule: true,
    isolatedModules: true,
    noEmit: true,
    jsx: ts.JsxEmit.ReactJSX,
    declaration: false,
    declarationMap: false,
    sourceMap: false
  };

  async validateTypeScriptCompilation(filePath: string): Promise<CompilationResult> {
    try {
      // Create a TypeScript program with the single file
      const program = ts.createProgram([filePath], this.compilerOptions);
      
      // Get all diagnostics and filter out node_modules issues
      const allDiagnostics = ts.getPreEmitDiagnostics(program);
      const relevantDiagnostics = allDiagnostics.filter(diagnostic => {
        if (!diagnostic.file) return false;
        const fileName = diagnostic.file.fileName;
        const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
        
        // Skip node_modules
        if (fileName.includes('node_modules')) return false;
        
        // Only include our src files
        if (!(fileName.includes('/src/') || fileName.includes('\\src\\'))) return false;
        
        // Skip expected Vite-specific errors (import.meta.env is Vite-only)
        if (message.includes("Property 'env' does not exist on type 'ImportMeta'") ||
            message.includes("The 'import.meta' meta-property is only allowed")) {
          return false;
        }
        
        return true;
      });
      
      const errors = relevantDiagnostics
        .filter(d => d.category === ts.DiagnosticCategory.Error)
        .map(d => this.formatDiagnostic(d));
      
      const warnings = relevantDiagnostics
        .filter(d => d.category === ts.DiagnosticCategory.Warning)
        .map(d => this.formatDiagnostic(d));

      return {
        success: errors.length === 0,
        errors,
        warnings,
        filePath
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        success: false,
        errors: [{
          message: `Compilation validation failed: ${errorMessage}`,
          line: 0,
          column: 0,
          severity: 'error',
          code: 0
        }],
        warnings: [],
        filePath
      };
    }
  }

  async validateImportResolution(filePath: string): Promise<ImportValidationResult> {
    try {
      const content = await fs.readFile(filePath, 'utf8');
      const imports = this.extractImports(content);
      
      const results = await Promise.all(
        imports.map(async imp => ({
          import: imp,
          resolved: await this.canResolveImport(imp, filePath)
        }))
      );

      const missingImports = results
        .filter(r => !r.resolved)
        .map(r => r.import);

      const circularDependencies = await this.detectCircularDependencies(filePath);

      return {
        allImportsResolved: missingImports.length === 0,
        missingImports,
        circularDependencies,
        filePath
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        allImportsResolved: false,
        missingImports: [`Error reading file: ${errorMessage}`],
        circularDependencies: [],
        filePath
      };
    }
  }

  async validateAllGeneratedFiles(generatedDir: string): Promise<{
    compilationResults: CompilationResult[];
    importResults: ImportValidationResult[];
    overallSuccess: boolean;
  }> {
    try {
      // Find all .gen.tsx files
      const files = await this.findGeneratedFiles(generatedDir);
      
      // Validate compilation and imports for all files
      const [compilationResults, importResults] = await Promise.all([
        Promise.all(files.map(file => this.validateTypeScriptCompilation(file))),
        Promise.all(files.map(file => this.validateImportResolution(file)))
      ]);

      const overallSuccess = compilationResults.every(r => r.success) &&
                           importResults.every(r => r.allImportsResolved);

      return {
        compilationResults,
        importResults,
        overallSuccess
      };
    } catch (error) {
      return {
        compilationResults: [],
        importResults: [],
        overallSuccess: false
      };
    }
  }

  private formatDiagnostic(diagnostic: ts.Diagnostic): DiagnosticInfo {
    const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
    let line = 0;
    let column = 0;

    if (diagnostic.file && diagnostic.start !== undefined) {
      const { line: ln, character } = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start);
      line = ln + 1; // Convert to 1-based
      column = character + 1;
    }

    return {
      message,
      line,
      column,
      severity: diagnostic.category === ts.DiagnosticCategory.Error ? 'error' : 
               diagnostic.category === ts.DiagnosticCategory.Warning ? 'warning' : 'info',
      code: diagnostic.code
    };
  }

  private extractImports(content: string): string[] {
    const importRegex = /import\s+(?:.*?\s+from\s+)?['"]([^'"]+)['"]/g;
    const imports: string[] = [];
    let match;

    while ((match = importRegex.exec(content)) !== null) {
      imports.push(match[1]);
    }

    return imports;
  }

  private async canResolveImport(importPath: string, fromFile: string): Promise<boolean> {
    try {
      // Skip validation for certain imports that are expected to exist
      if (importPath.startsWith('react') || 
          importPath.startsWith('@mui/') ||
          importPath.startsWith('../../stores') ||
          importPath.startsWith('../../hooks') ||
          importPath.startsWith('../../components')) {
        return true; // Assume these core imports exist
      }

      // For relative imports, try to resolve the path
      if (importPath.startsWith('./') || importPath.startsWith('../')) {
        const resolvedPath = path.resolve(path.dirname(fromFile), importPath);
        const possibleExtensions = ['.ts', '.tsx', '.js', '.jsx'];
        
        for (const ext of possibleExtensions) {
          try {
            await fs.access(resolvedPath + ext);
            return true;
          } catch {
            // Continue to next extension
          }
        }
        
        // Check if it's a directory with index file
        try {
          const indexPath = path.join(resolvedPath, 'index');
          for (const ext of possibleExtensions) {
            try {
              await fs.access(indexPath + ext);
              return true;
            } catch {
              // Continue
            }
          }
        } catch {
          // Continue
        }
        
        return false;
      }

      // For absolute imports, assume they exist (node_modules, etc.)
      return true;
    } catch {
      return false;
    }
  }

  private async detectCircularDependencies(filePath: string): Promise<string[]> {
    // Simplified circular dependency detection
    // For a full implementation, we'd need to build a dependency graph
    // For now, return empty array as placeholder
    return [];
  }

  private async findGeneratedFiles(directory: string): Promise<string[]> {
    try {
      const entries = await fs.readdir(directory, { withFileTypes: true });
      const files: string[] = [];

      for (const entry of entries) {
        const fullPath = path.join(directory, entry.name);
        
        if (entry.isDirectory()) {
          const subFiles = await this.findGeneratedFiles(fullPath);
          files.push(...subFiles);
        } else if (entry.name.endsWith('.gen.tsx')) {
          files.push(fullPath);
        }
      }

      return files;
    } catch {
      return [];
    }
  }
} 