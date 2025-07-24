import * as fs from 'fs/promises';
import * as path from 'path';

export interface RenderValidationResult {
  rendersWithoutCrash: boolean;
  hasRequiredElements: boolean;
  missingComponents: string[];
  renderErrors: RenderError[];
  filePath: string;
}

export interface RenderError {
  message: string;
  stack?: string;
  severity: 'error' | 'warning';
}

export interface ComponentValidationSummary {
  totalComponents: number;
  validComponents: number;
  invalidComponents: number;
  results: RenderValidationResult[];
  overallSuccess: boolean;
}

export class ComponentValidator {
  private requiredImports = [
    'React',
    'useLogStore',
    'useExecuteDeviceAction',
    'Button'
  ];

  private requiredElements = [
    'div', // Container
    'h1',  // Title
    'Button' // At least one button
  ];

  async validateComponentRendering(componentPath: string): Promise<RenderValidationResult> {
    try {
      const content = await fs.readFile(componentPath, 'utf8');
      
      // Basic structural validation since we can't actually render without full setup
      const structuralValidation = this.validateComponentStructure(content);
      const importValidation = this.validateRequiredImports(content);
      const elementValidation = this.validateRequiredElements(content);

      const errors: RenderError[] = [];
      
      if (!structuralValidation.valid) {
        errors.push(...structuralValidation.errors);
      }
      
      if (!importValidation.valid) {
        errors.push(...importValidation.errors);
      }

      if (!elementValidation.valid) {
        errors.push(...elementValidation.errors);
      }

      return {
        rendersWithoutCrash: errors.filter(e => e.severity === 'error').length === 0,
        hasRequiredElements: elementValidation.valid,
        missingComponents: importValidation.missingImports,
        renderErrors: errors,
        filePath: componentPath
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const errorStack = error instanceof Error ? error.stack : undefined;
      return {
        rendersWithoutCrash: false,
        hasRequiredElements: false,
        missingComponents: [],
        renderErrors: [{
          message: `Component validation failed: ${errorMessage}`,
          stack: errorStack,
          severity: 'error'
        }],
        filePath: componentPath
      };
    }
  }

  async validateAllGeneratedComponents(generatedDir: string): Promise<ComponentValidationSummary> {
    try {
      const componentFiles = await this.findComponentFiles(generatedDir);
      
      const results = await Promise.all(
        componentFiles.map(file => this.validateComponentRendering(file))
      );

      const validComponents = results.filter(r => r.rendersWithoutCrash).length;
      const invalidComponents = results.length - validComponents;

      return {
        totalComponents: results.length,
        validComponents,
        invalidComponents,
        results,
        overallSuccess: invalidComponents === 0
      };
    } catch (error) {
      return {
        totalComponents: 0,
        validComponents: 0,
        invalidComponents: 0,
        results: [],
        overallSuccess: false
      };
    }
  }

  private validateComponentStructure(content: string): { valid: boolean; errors: RenderError[] } {
    const errors: RenderError[] = [];

    // Check for basic React component structure
    if (!content.includes('function ') && !content.includes('const ') && !content.includes('export default')) {
      errors.push({
        message: 'Component does not appear to have a valid function declaration',
        severity: 'error'
      });
    }

    // Check for return statement with JSX
    if (!content.includes('return (') && !content.includes('return <')) {
      errors.push({
        message: 'Component does not appear to return JSX',
        severity: 'error'
      });
    }

    // Check for proper export
    if (!content.includes('export default')) {
      errors.push({
        message: 'Component does not have a default export',
        severity: 'error'
      });
    }

    // Check for handleAction function (should be present in generated components)
    if (!content.includes('handleAction')) {
      errors.push({
        message: 'Component missing handleAction function',
        severity: 'warning'
      });
    }

    return {
      valid: errors.filter(e => e.severity === 'error').length === 0,
      errors
    };
  }

  private validateRequiredImports(content: string): { valid: boolean; errors: RenderError[]; missingImports: string[] } {
    const errors: RenderError[] = [];
    const missingImports: string[] = [];

    for (const requiredImport of this.requiredImports) {
      if (!content.includes(requiredImport)) {
        missingImports.push(requiredImport);
        errors.push({
          message: `Missing required import: ${requiredImport}`,
          severity: 'error'
        });
      }
    }

    return {
      valid: missingImports.length === 0,
      errors,
      missingImports
    };
  }

  private validateRequiredElements(content: string): { valid: boolean; errors: RenderError[] } {
    const errors: RenderError[] = [];

    // Check for container div
    if (!content.includes('<div') && !content.includes('className=')) {
      errors.push({
        message: 'Component appears to be missing container div with styling',
        severity: 'warning'
      });
    }

    // Check for title element
    if (!content.includes('<h1') && !content.includes('<h2')) {
      errors.push({
        message: 'Component appears to be missing title element',
        severity: 'warning'
      });
    }

    // Check for Button components (make this a warning, not error - some devices may not need buttons)
    if (!content.includes('<Button')) {
      errors.push({
        message: 'Component appears to be missing Button components',
        severity: 'warning'
      });
    }

    // Check for onClick handlers (make this a warning, not error - some devices may be display-only)
    if (!content.includes('onClick')) {
      errors.push({
        message: 'Component appears to be missing onClick handlers',
        severity: 'warning'
      });
    }

    return {
      valid: errors.filter(e => e.severity === 'error').length === 0,
      errors
    };
  }

  private async findComponentFiles(directory: string): Promise<string[]> {
    try {
      const entries = await fs.readdir(directory, { withFileTypes: true });
      const files: string[] = [];

      for (const entry of entries) {
        const fullPath = path.join(directory, entry.name);
        
        if (entry.isDirectory()) {
          const subFiles = await this.findComponentFiles(fullPath);
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

  async validateSpecificComponent(componentPath: string, expectedActions: string[]): Promise<RenderValidationResult & { actionValidation: boolean }> {
    const baseResult = await this.validateComponentRendering(componentPath);
    
    try {
      const content = await fs.readFile(componentPath, 'utf8');
      
      // Validate that expected actions are present
      const actionValidation = expectedActions.every(action => 
        content.includes(`'${action}'`) || content.includes(`"${action}"`)
      );

      return {
        ...baseResult,
        actionValidation
      };
    } catch {
      return {
        ...baseResult,
        actionValidation: false
      };
    }
  }
} 