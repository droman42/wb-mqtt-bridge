export interface GenerationMetrics {
  totalGenerations: number;
  successfulGenerations: number;
  failedGenerations: number;
  averageGenerationTime: number;
  deviceClassBreakdown: Record<string, DeviceClassMetrics>;
  totalDuration: number;
}

export interface DeviceClassMetrics {
  count: number;
  successCount: number;
  failureCount: number;
  averageTime: number;
  totalTime: number;
}

export interface PerformanceTimer {
  deviceId: string;
  startTime: number;
  complete: (success: boolean, deviceClass: string) => void;
}

export class PerformanceMonitor {
  private metrics: GenerationMetrics = {
    totalGenerations: 0,
    successfulGenerations: 0,
    failedGenerations: 0,
    averageGenerationTime: 0,
    deviceClassBreakdown: {},
    totalDuration: 0
  };
  
  private sessionStartTime: number = Date.now();
  
  trackGenerationStart(deviceId: string): PerformanceTimer {
    const startTime = Date.now();
    
    return {
      deviceId,
      startTime,
      complete: (success: boolean, deviceClass: string) => {
        const duration = Date.now() - startTime;
        this.recordGeneration(success, deviceClass, duration);
      }
    };
  }
  
  recordGeneration(success: boolean, deviceClass: string, duration: number): void {
    // Update global metrics
    this.metrics.totalGenerations++;
    this.metrics.totalDuration += duration;
    
    if (success) {
      this.metrics.successfulGenerations++;
    } else {
      this.metrics.failedGenerations++;
    }
    
    this.updateAverageTime(duration);
    this.updateDeviceClassBreakdown(deviceClass, success, duration);
  }
  
  private updateAverageTime(duration: number): void {
    // Calculate rolling average
    const totalTime = (this.metrics.averageGenerationTime * (this.metrics.totalGenerations - 1)) + duration;
    this.metrics.averageGenerationTime = totalTime / this.metrics.totalGenerations;
  }
  
  private updateDeviceClassBreakdown(deviceClass: string, success: boolean, duration: number): void {
    if (!this.metrics.deviceClassBreakdown[deviceClass]) {
      this.metrics.deviceClassBreakdown[deviceClass] = {
        count: 0,
        successCount: 0,
        failureCount: 0,
        averageTime: 0,
        totalTime: 0
      };
    }
    
    const classMetrics = this.metrics.deviceClassBreakdown[deviceClass];
    classMetrics.count++;
    classMetrics.totalTime += duration;
    
    if (success) {
      classMetrics.successCount++;
    } else {
      classMetrics.failureCount++;
    }
    
    classMetrics.averageTime = classMetrics.totalTime / classMetrics.count;
  }
  
  getMetrics(): GenerationMetrics {
    return { ...this.metrics };
  }
  
  getSessionDuration(): number {
    return Date.now() - this.sessionStartTime;
  }
  
  getSuccessRate(): number {
    if (this.metrics.totalGenerations === 0) return 0;
    return (this.metrics.successfulGenerations / this.metrics.totalGenerations) * 100;
  }
  
  getSlowestDeviceClass(): { deviceClass: string; averageTime: number } | null {
    const classes = Object.entries(this.metrics.deviceClassBreakdown);
    if (classes.length === 0) return null;
    
    const slowest = classes.reduce((prev, [deviceClass, metrics]) => 
      metrics.averageTime > prev.averageTime 
        ? { deviceClass, averageTime: metrics.averageTime }
        : prev
    , { deviceClass: '', averageTime: 0 });
    
    return slowest.deviceClass ? slowest : null;
  }
  
  generateReport(): string {
    const sessionDuration = this.getSessionDuration();
    const successRate = this.getSuccessRate();
    const slowest = this.getSlowestDeviceClass();
    
    let report = `
📊 Performance Report
━━━━━━━━━━━━━━━━━━━━━━━━

⏱️  Session Duration: ${Math.round(sessionDuration / 1000)}s
📈 Total Generations: ${this.metrics.totalGenerations}
✅ Successful: ${this.metrics.successfulGenerations}
❌ Failed: ${this.metrics.failedGenerations}
🎯 Success Rate: ${successRate.toFixed(1)}%
⚡ Average Time: ${Math.round(this.metrics.averageGenerationTime)}ms

📋 Device Class Breakdown:
━━━━━━━━━━━━━━━━━━━━━━━━
`;

    Object.entries(this.metrics.deviceClassBreakdown).forEach(([deviceClass, metrics]) => {
      const classSuccessRate = (metrics.successCount / metrics.count) * 100;
      report += `
${deviceClass}:
  • Total: ${metrics.count}
  • Success: ${metrics.successCount} (${classSuccessRate.toFixed(1)}%)
  • Avg Time: ${Math.round(metrics.averageTime)}ms`;
    });
    
    if (slowest) {
      report += `

🐌 Slowest Device Class: ${slowest.deviceClass} (${Math.round(slowest.averageTime)}ms)`;
    }
    
    return report;
  }
  
  reset(): void {
    this.metrics = {
      totalGenerations: 0,
      successfulGenerations: 0,
      failedGenerations: 0,
      averageGenerationTime: 0,
      deviceClassBreakdown: {},
      totalDuration: 0
    };
    this.sessionStartTime = Date.now();
  }
} 