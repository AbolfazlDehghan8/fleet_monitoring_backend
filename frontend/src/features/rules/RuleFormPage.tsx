import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, Loader2, Save } from 'lucide-react';
import { Controller, useForm } from 'react-hook-form';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/use-toast';
import { RULE_METRIC_RANGES, RULE_METRICS, RULE_OPERATORS, SEVERITIES } from '@/constants/statuses';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';

import { useCreateRule, useRule, useUpdateRule } from './hooks';

function useRuleSchema(t: (key: TranslationKey, vars?: Record<string, string | number>) => string) {
  return z
    .object({
      name: z.string().min(1, t('ruleForm.nameRequired')).max(200, t('validation.maxLength', { max: 200 })),
      description: z.string().max(1000, t('validation.maxLength', { max: 1000 })).optional(),
      metric: z.enum(['speed', 'engine_temperature', 'battery_voltage', 'fuel_level', 'odometer']),
      operator: z.enum(['gt', 'gte', 'lt', 'lte', 'eq']),
      threshold: z.coerce.number({ invalid_type_error: t('ruleForm.thresholdInvalid') }),
      severity: z.enum(['low', 'medium', 'high', 'critical']),
      is_active: z.boolean(),
    })
    .superRefine((values, ctx) => {
      // Mirrors the backend's physical range per metric (see RULE_METRIC_RANGES) — a
      // threshold outside it could never fire and the server rejects it.
      const range = RULE_METRIC_RANGES[values.metric];
      if (Number.isFinite(values.threshold) && (values.threshold < range.min || values.threshold > range.max)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['threshold'],
          message: t('ruleForm.thresholdOutOfRange', { min: range.min, max: range.max }),
        });
      }
    });
}

type RuleFormValues = {
  name: string;
  description?: string;
  metric: 'speed' | 'engine_temperature' | 'battery_voltage' | 'fuel_level' | 'odometer';
  operator: 'gt' | 'gte' | 'lt' | 'lte' | 'eq';
  threshold: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  is_active: boolean;
};

export function RuleFormPage() {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const isEditing = Boolean(params.id);
  const ruleId = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const ruleQuery = useRule(ruleId);
  const createMutation = useCreateRule();
  const updateMutation = useUpdateRule(ruleId ?? -1);
  const ruleSchema = useRuleSchema(t);

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RuleFormValues>({
    resolver: zodResolver(ruleSchema),
    values: ruleQuery.data
      ? {
          name: ruleQuery.data.name,
          description: ruleQuery.data.description,
          metric: ruleQuery.data.metric,
          operator: ruleQuery.data.operator,
          threshold: ruleQuery.data.threshold,
          severity: ruleQuery.data.severity,
          is_active: ruleQuery.data.is_active,
        }
      : undefined,
    defaultValues: {
      name: '',
      description: '',
      metric: 'speed',
      operator: 'gt',
      threshold: 0,
      severity: 'medium',
      is_active: true,
    },
  });

  if (isEditing && ruleQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t('ruleForm.loadingRule')}</p>;
  }

  if (isEditing && ruleQuery.isError) {
    return <ErrorState onRetry={() => void ruleQuery.refetch()} title={t('ruleForm.unableToLoad')} />;
  }

  async function onSubmit(values: RuleFormValues) {
    try {
      if (isEditing && ruleId !== undefined) {
        await updateMutation.mutateAsync(values);
        toast({ title: t('ruleForm.ruleUpdated'), variant: 'success' });
      } else {
        await createMutation.mutateAsync(values);
        toast({ title: t('ruleForm.ruleCreated'), variant: 'success' });
      }
      navigate('/rules');
    } catch (error) {
      toast({
        title: t('ruleForm.couldNotSave'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/rules">
            <ArrowLeft className="size-3.5" />
            {t('ruleForm.backToRules')}
          </Link>
        </Button>
        <PageHeader
          title={isEditing ? t('ruleForm.editRule') : t('ruleForm.newRule')}
          description={t('ruleForm.desc')}
        />
      </div>

      <Card className="max-w-2xl">
        <CardContent className="pt-5">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="name">{t('ruleForm.ruleName')}</Label>
              <Input id="name" placeholder="High engine temperature" {...register('name')} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="description">{t('ruleForm.description')}</Label>
              <Textarea
                id="description"
                placeholder={t('ruleForm.descriptionPlaceholder')}
                {...register('description')}
              />
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label>{t('ruleForm.metric')}</Label>
                <Controller
                  control={control}
                  name="metric"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RULE_METRICS.map((m) => (
                          <SelectItem key={m.value} value={m.value}>
                            {t(`ruleMetric.${m.value}` as TranslationKey)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="space-y-1.5">
                <Label>{t('ruleForm.operator')}</Label>
                <Controller
                  control={control}
                  name="operator"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RULE_OPERATORS.map((op) => (
                          <SelectItem key={op.value} value={op.value}>
                            {op.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="threshold">{t('ruleForm.threshold')}</Label>
                <Input id="threshold" type="number" step="any" {...register('threshold')} />
                {errors.threshold ? (
                  <p className="text-xs text-destructive">{errors.threshold.message}</p>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {t('ruleForm.thresholdRangeHint', RULE_METRIC_RANGES[watch('metric')])}
                  </p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>{t('ruleForm.severity')}</Label>
                <Controller
                  control={control}
                  name="severity"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.values(SEVERITIES).map((severity) => (
                          <SelectItem key={severity} value={severity}>
                            {t(`severity.${severity}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="flex items-center justify-between rounded-md border border-input px-3 py-2">
                <Label htmlFor="is_active" className="cursor-pointer">
                  {t('ruleForm.ruleEnabled')}
                </Label>
                <Controller
                  control={control}
                  name="is_active"
                  render={({ field }) => (
                    <Switch id="is_active" checked={field.value} onCheckedChange={field.onChange} />
                  )}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => navigate('/rules')}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                {isEditing ? t('adminForm.saveChanges') : t('ruleForm.createRule')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
