import type { ProcessedAction } from '../../types/ProcessedDevice';

export class PointerPadGenerator {
  generate(actions: ProcessedAction[]): string {
    const moveAction = actions.find(a => 
      a.actionName.includes('move_cursor') || 
      a.actionName.includes('move') ||
      a.actionName.includes('cursor')
    );
    const clickAction = actions.find(a => 
      a.actionName.includes('click') || 
      a.actionName.includes('select')
    );
    const scrollAction = actions.find(a => 
      a.actionName.includes('scroll')
    );
    
    return `
          <div className="pointer-pad-container">
            <div className="text-center mb-4">
              <h3 className="text-lg font-medium">Pointer Control</h3>
              <p className="text-sm text-gray-600">Move cursor and click to control</p>
            </div>
            <PointerPad
              ${moveAction ? `onMove={(x, y) => handleAction('${moveAction.actionName}', { x, y })}` : ''}
              ${clickAction ? `onClick={() => handleAction('${clickAction.actionName}')}` : ''}
              ${scrollAction ? `onScroll={(deltaY) => handleAction('${scrollAction.actionName}', { deltaY })}` : ''}
              className="w-full h-64 border rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              style={{ touchAction: 'none' }}
            />
            ${this.generateActionButtons(actions)}
          </div>
    `;
  }
  
  private generateActionButtons(actions: ProcessedAction[]): string {
    // Generate buttons for non-pointer actions
    const nonPointerActions = actions.filter(action => 
      !action.uiHints.isPointerAction &&
      !action.actionName.includes('move') &&
      !action.actionName.includes('cursor')
    );
    
    if (nonPointerActions.length === 0) {
      return '';
    }
    
    return `
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              ${nonPointerActions.map(action => this.generateButton(action)).join('\n              ')}
            </div>
    `;
  }
  
  private generateButton(action: ProcessedAction): string {
    const IconComponent = action.icon.iconName;
    return `
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAction('${action.actionName}')}
                className="flex items-center gap-1"
                title="${action.description}"
              >
                <${IconComponent} className="w-3 h-3" />
                ${action.displayName}
              </Button>`;
  }
} 