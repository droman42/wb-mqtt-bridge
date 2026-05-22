import type { ProcessedAction } from '../../types/ProcessedDevice';

export class SliderControlGenerator {
  generate(actions: ProcessedAction[]): string {
    return actions.map(action => {
      const rangeParam = action.parameters.find(p => p.type === 'range');
      if (!rangeParam) {
        return this.generateButton(action);
      }
      
      return this.generateSlider(action, rangeParam);
    }).join('\n');
  }
  
  private generateSlider(action: ProcessedAction, rangeParam: import('../../types/ProcessedDevice').ProcessedParameter): string {
    const IconComponent = action.icon.iconName;
    const minValue = rangeParam.min ?? 0;
    const maxValue = rangeParam.max ?? 100;
    const defaultValue = rangeParam.default ?? minValue;
    const step = this.calculateStep(minValue, maxValue);
    
    return `
          <div className="slider-control space-y-3">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm font-medium">
                <${IconComponent} className="w-4 h-4" />
                ${action.displayName}
              </label>
              <span className="text-xs text-gray-500">
                {${rangeParam.name}Value}${this.getUnitSuffix(action.actionName)}
              </span>
            </div>
            <div className="space-y-2">
              <SliderControl
                min={${minValue}}
                max={${maxValue}}
                step={${step}}
                defaultValue={${defaultValue}}
                value={${rangeParam.name}Value}
                onValueChange={(value) => {
                  set${this.capitalizeFirst(rangeParam.name)}Value(value);
                  handleAction('${action.actionName}', { ${rangeParam.name}: value });
                }}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-400">
                <span>${minValue}${this.getUnitSuffix(action.actionName)}</span>
                <span>${maxValue}${this.getUnitSuffix(action.actionName)}</span>
              </div>
            </div>
            ${action.description ? `<p className="text-xs text-gray-500">${action.description}</p>` : ''}
          </div>
    `;
  }
  
  private generateButton(action: ProcessedAction): string {
    const IconComponent = action.icon.iconName;
    const buttonStyle = action.uiHints.buttonStyle || 'secondary';
    
    return `
          <div className="button-control">
            <Button
              variant="${buttonStyle}"
              size="default"
              onClick={() => handleAction('${action.actionName}')}
              className="w-full flex items-center justify-center gap-2"
              title="${action.description}"
            >
              <${IconComponent} className="w-4 h-4" />
              ${action.displayName}
            </Button>
            ${action.description ? `<p className="text-xs text-gray-500 mt-1 text-center">${action.description}</p>` : ''}
          </div>
    `;
  }
  
  private calculateStep(min: number, max: number): number {
    const range = max - min;
    if (range <= 10) return 1;
    if (range <= 100) return 5;
    return 10;
  }
  
  private getUnitSuffix(actionName: string): string {
    const cleanName = actionName.toLowerCase();
    if (cleanName.includes('volume')) return '%';
    if (cleanName.includes('speed')) return '';
    if (cleanName.includes('temperature') || cleanName.includes('temp')) return '°';
    if (cleanName.includes('timer') || cleanName.includes('time')) return 'min';
    if (cleanName.includes('brightness') || cleanName.includes('light')) return '%';
    return '';
  }
  
  private capitalizeFirst(str: string): string {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }
  
  generateStateVariables(actions: ProcessedAction[]): string {
    const rangeActions = actions.filter(action => 
      action.parameters.some(p => p.type === 'range')
    );
    
    if (rangeActions.length === 0) {
      return '';
    }
    
    return rangeActions.map(action => {
      const rangeParam = action.parameters.find(p => p.type === 'range');
      if (!rangeParam) return '';
      
      const defaultValue = rangeParam.default ?? rangeParam.min ?? 0;
      return `  const [${rangeParam.name}Value, set${this.capitalizeFirst(rangeParam.name)}Value] = useState(${defaultValue});`;
    }).join('\n');
  }
} 