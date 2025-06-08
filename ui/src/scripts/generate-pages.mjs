#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { glob } from 'glob';
import YAML from 'yaml';
import Ajv from 'ajv';

const ajv = new Ajv();

// Prompt schema for validation
const promptSchema = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    title: {
      type: 'object',
      properties: {
        en: { type: 'string' },
        ru: { type: 'string' }
      },
      required: ['en', 'ru']
    },
    menu: {
      type: 'object',
      properties: {
        up: { type: 'string' },
        down: { type: 'string' },
        left: { type: 'string' },
        right: { type: 'string' },
        ok: { type: 'string' },
        aux1: { type: 'string' },
        aux2: { type: 'string' },
        aux3: { type: 'string' },
        aux4: { type: 'string' }
      }
    },
    sliders: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          min: { type: 'number' },
          max: { type: 'number' },
          step: { type: 'number' },
          icon: { type: 'string' },
          ticks: { type: 'array', items: { type: 'number' } },
          transport: { type: 'string', enum: ['api', 'mqtt'] },
          payload: { type: 'object' }
        },
        required: ['id', 'min', 'max']
      }
    },
    pointer: {
      type: 'object',
      properties: {
        mode: { type: 'string', enum: ['relative', 'absolute'] },
        sensitivity: { type: 'number' },
        transport: { type: 'string', enum: ['api', 'mqtt'] },
        hintIcon: { oneOf: [{ type: 'string' }, { type: 'boolean' }] }
      },
      required: ['mode']
    },
    buttons: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          icon: { type: 'string' },
          label: {
            type: 'object',
            properties: {
              en: { type: 'string' },
              ru: { type: 'string' }
            }
          },
          transport: { type: 'string', enum: ['api', 'mqtt'] },
          payload: { type: 'object' },
          promptForInput: {
            type: 'object',
            properties: {
              label: {
                type: 'object',
                properties: {
                  en: { type: 'string' },
                  ru: { type: 'string' }
                },
                required: ['en', 'ru']
              },
              paramKey: { type: 'string' }
            },
            required: ['label', 'paramKey']
          },
          holdable: { type: 'boolean' }
        },
        required: ['id']
      }
    },
    hideStatePanel: { type: 'boolean' }
  },
  required: ['id', 'title']
};

const validate = ajv.compile(promptSchema);

async function generatePages() {
  console.log('🔄 Generating pages from prompts...');

  // Ensure directories exist
  const pagesDir = 'src/pages';
  if (!fs.existsSync(pagesDir)) {
    fs.mkdirSync(pagesDir, { recursive: true });
  }

  // Find all prompt files
  const promptFiles = await glob('src/prompts/**/*.prompt.{yaml,yml,ts,js}');
  console.log(`📁 Found ${promptFiles.length} prompt files`);

  const generatedPages = [];
  const errors = [];

  for (const promptFile of promptFiles) {
    try {
      console.log(`📄 Processing ${promptFile}...`);
      
      let promptData;
      const ext = path.extname(promptFile);
      
      if (ext === '.yaml' || ext === '.yml') {
        const content = fs.readFileSync(promptFile, 'utf8');
        promptData = YAML.parse(content);
      } else if (ext === '.ts' || ext === '.js') {
        // Dynamic import for JS/TS files
        const module = await import(path.resolve(promptFile));
        promptData = module.default || module;
      }

      // Validate against schema
      if (!validate(promptData)) {
        throw new Error(`Validation failed: ${JSON.stringify(validate.errors, null, 2)}`);
      }

      // Generate React component
      const componentCode = generateReactComponent(promptData);
      const outputPath = path.join(pagesDir, `${promptData.id}.gen.tsx`);
      
      fs.writeFileSync(outputPath, componentCode);
      generatedPages.push({
        id: promptData.id,
        title: promptData.title,
        path: outputPath
      });

      console.log(`✅ Generated ${outputPath}`);
    } catch (error) {
      console.error(`❌ Error processing ${promptFile}:`, error.message);
      errors.push({ file: promptFile, error: error.message });
    }
  }

  // Generate router manifest
  const manifestPath = 'src/pages/manifest.json';
  fs.writeFileSync(manifestPath, JSON.stringify(generatedPages, null, 2));
  console.log(`📋 Generated manifest: ${manifestPath}`);

  // Generate router index
  generateRouterIndex(generatedPages);

  console.log(`🎉 Generated ${generatedPages.length} pages successfully`);
  if (errors.length > 0) {
    console.log(`⚠️  ${errors.length} errors occurred`);
    errors.forEach(({ file, error }) => {
      console.log(`   ${file}: ${error}`);
    });
  }
}

function generateReactComponent(prompt) {
  return `// Auto-generated from prompt file - DO NOT EDIT
import React from 'react';
import { useLogStore } from '../stores/useLogStore';
import NavCluster from '../components/NavCluster';
import SliderControl from '../components/SliderControl';
import PointerPad from '../components/PointerPad';
import { Button } from '../components/ui/button';

function ${prompt.id.charAt(0).toUpperCase() + prompt.id.slice(1)}Page() {
  const { addLog } = useLogStore();

  const handleAction = (action: string, payload?: any) => {
    addLog({
      level: 'info',
      message: \`Action: \${action}\`,
      details: payload
    });
    console.log('Action:', action, payload);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">${prompt.title.en}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Controls Column */}
        <div className="space-y-6">
          ${prompt.sliders ? generateSlidersCode(prompt.sliders) : ''}
          
          ${prompt.menu ? generateNavClusterCode(prompt.menu) : ''}
          
          ${prompt.buttons ? generateButtonsCode(prompt.buttons) : ''}
        </div>

        {/* Pointer Column */}
        <div className="space-y-6">
          ${prompt.pointer ? generatePointerCode(prompt.pointer) : ''}
        </div>
      </div>
    </div>
  );
}

export default ${prompt.id.charAt(0).toUpperCase() + prompt.id.slice(1)}Page;
`;
}

function generateSlidersCode(sliders) {
  return sliders.map(slider => `
          <SliderControl
            id="${slider.id}"
            min={${slider.min}}
            max={${slider.max}}
            ${slider.step ? `step={${slider.step}}` : ''}
            value={50}
            ${slider.icon ? `icon="${slider.icon}"` : ''}
            ${slider.ticks ? `ticks={${JSON.stringify(slider.ticks)}}` : ''}
            onChange={(value) => handleAction('slider:${slider.id}', { value, transport: '${slider.transport || 'api'}' })}
          />`).join('\n');
}

function generateNavClusterCode(menu) {
  return `
          <div className="flex justify-center">
            <NavCluster
              ${menu.up ? `onUp={() => handleAction('${menu.up}')}` : ''}
              ${menu.down ? `onDown={() => handleAction('${menu.down}')}` : ''}
              ${menu.left ? `onLeft={() => handleAction('${menu.left}')}` : ''}
              ${menu.right ? `onRight={() => handleAction('${menu.right}')}` : ''}
              ${menu.ok ? `onOk={() => handleAction('${menu.ok}')}` : ''}
              ${menu.aux1 ? `onAux1={() => handleAction('${menu.aux1}')}` : ''}
              ${menu.aux2 ? `onAux2={() => handleAction('${menu.aux2}')}` : ''}
              ${menu.aux3 ? `onAux3={() => handleAction('${menu.aux3}')}` : ''}
              ${menu.aux4 ? `onAux4={() => handleAction('${menu.aux4}')}` : ''}
            />
          </div>`;
}

function generateButtonsCode(buttons) {
  return buttons.map(button => `
          <Button
            onClick={() => handleAction('button:${button.id}', { transport: '${button.transport || 'api'}' })}
            className="w-full"
          >
            ${button.label ? button.label.en : button.id}
          </Button>`).join('\n');
}

function generatePointerCode(pointer) {
  return `
          <PointerPad
            mode="${pointer.mode}"
            ${pointer.sensitivity ? `sensitivity={${pointer.sensitivity}}` : ''}
            ${pointer.hintIcon !== undefined ? `hintIcon={${typeof pointer.hintIcon === 'string' ? `"${pointer.hintIcon}"` : pointer.hintIcon}}` : ''}
            onMove={(x, y) => handleAction('pointer:move', { x, y, mode: '${pointer.mode}', transport: '${pointer.transport || 'api'}' })}
          />`;
}

function generateRouterIndex(pages) {
  const imports = pages.map(page => 
    `import ${page.id.charAt(0).toUpperCase() + page.id.slice(1)}Page from './${page.id}.gen';`
  ).join('\n');

  const exports = pages.map(page => 
    `  ${page.id}: ${page.id.charAt(0).toUpperCase() + page.id.slice(1)}Page,`
  ).join('\n');

  const code = `// Auto-generated router index - DO NOT EDIT
${imports}

export const generatedPages = {
${exports}
};

export const pageManifest = ${JSON.stringify(pages, null, 2)};
`;

  fs.writeFileSync('src/pages/index.gen.ts', code);
  console.log('📦 Generated router index: src/pages/index.gen.ts');
}

// Run the generator
generatePages().catch(console.error); 