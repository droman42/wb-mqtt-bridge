import React from 'react';
import { Icon } from './icons';
import { useLogStore } from '../stores/useLogStore';
import { useSettingsStore } from '../stores/useSettingsStore';
import { formatTimestamp } from '../lib/utils';
import { Button } from './ui/button';

interface LogPanelProps {
  isOpen: boolean;
  className?: string;
}

function LogPanel({ isOpen, className }: LogPanelProps) {
  const { entries, clearLogs } = useLogStore();
  const { toggleLogPanel } = useSettingsStore();

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'text-red-500';
      case 'warn': return 'text-yellow-500';
      case 'info': return 'text-blue-500';
      default: return 'text-foreground';
    }
  };

  return (
    <div className={`bg-card border-t border-border ${className}`}>
      {/* Header - always visible */}
      <div className="h-12 flex items-center justify-between px-4 border-b border-border">
        <div className="flex items-center space-x-2">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={toggleLogPanel}
            className="flex items-center space-x-1"
          >
            {isOpen ? (
              <Icon library="material" name="KeyboardArrowDown" size="sm" fallback="arrow-down" className="h-4 w-4" />
            ) : (
              <Icon library="material" name="KeyboardArrowUp" size="sm" fallback="arrow-up" className="h-4 w-4" />
            )}
            <span className="text-sm font-medium">Logs ({entries.length})</span>
          </Button>
        </div>

        {isOpen && (
          <Button 
            variant="ghost" 
            size="sm"
            onClick={clearLogs}
            className="flex items-center space-x-1"
          >
            <Icon library="material" name="Delete" size="sm" fallback="trash" className="h-4 w-4" />
            <span className="text-sm">Clear</span>
          </Button>
        )}
      </div>

      {/* Content - only visible when open */}
      {isOpen && (
        <div className="flex-1 overflow-auto p-4">
          {entries.length === 0 ? (
            <p className="text-muted-foreground text-sm">No logs yet</p>
          ) : (
            <div className="space-y-2">
              {entries.map((entry) => (
                <div key={entry.id} className="text-sm font-mono">
                  <div className="flex items-start space-x-2">
                    <span className="text-muted-foreground text-xs">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                    <span className={`text-xs font-medium ${getLevelColor(entry.level)}`}>
                      [{entry.level.toUpperCase()}]
                    </span>
                    <span className="flex-1">{entry.message}</span>
                  </div>
                  {entry.details && (
                    <div className="ml-20 mt-1 text-xs text-muted-foreground">
                      {JSON.stringify(entry.details, null, 2)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LogPanel; 