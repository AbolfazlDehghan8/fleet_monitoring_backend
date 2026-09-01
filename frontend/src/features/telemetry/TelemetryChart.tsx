import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useLanguage } from '@/app/LanguageContext';
import { ChartSkeleton } from '@/components/shared/LoadingSkeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { formatTime } from '@/utils/formatters';
import type { TelemetryLog } from '@/types/telemetry';

interface TelemetryChartProps {
  data: TelemetryLog[];
  metric: keyof Pick<TelemetryLog, 'speed' | 'fuel_level' | 'engine_temperature' | 'battery_voltage'>;
  label: string;
  unit: string;
  color: string;
  isLoading?: boolean;
}

export function TelemetryChart({ data, metric, label, unit, color, isLoading }: TelemetryChartProps) {
  const { t } = useLanguage();
  if (isLoading) return <ChartSkeleton />;

  if (data.length === 0) {
    return <EmptyState title={t('telemetry.noData')} description={t('telemetry.noDataDesc')} />;
  }

  const chartData = [...data]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((log) => ({ timestamp: log.timestamp, value: log[metric] }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={(value: string) => formatTime(value)}
            className="text-xs"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            className="text-xs"
            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
            width={44}
            unit={unit}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(value: string) => formatTime(value)}
            formatter={(value: number) => [`${value}${unit}`, label]}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} isAnimationActive />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
