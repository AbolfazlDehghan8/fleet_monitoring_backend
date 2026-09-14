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
import { PasswordInput } from '@/components/ui/password-input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';

import { useAdminUser, useCreateAdminUser, useUpdateAdminUser } from './hooks';

function useSchemas(t: (key: TranslationKey, vars?: Record<string, string | number>) => string) {
  const createSchema = z
    .object({
      username: z.string().min(1, t('login.errorUsernameRequired')).max(150, t('validation.maxLength', { max: 150 })),
      email: z.string().email(t('register.errorEmailInvalid')),
      password: z.string().min(8, t('register.errorPasswordMin')),
      password_confirm: z.string().min(8, t('register.errorPasswordMin')),
      role: z.enum(['admin', 'fleet_manager', 'driver']),
      first_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
      last_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
    })
    .refine((data) => data.password === data.password_confirm, {
      message: t('register.errorPasswordMismatch'),
      path: ['password_confirm'],
    });

  const editSchema = z.object({
    email: z.string().email(t('register.errorEmailInvalid')).optional().or(z.literal('')),
    role: z.enum(['admin', 'fleet_manager', 'driver']),
    first_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
    last_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
    is_active: z.boolean(),
  });

  return { createSchema, editSchema };
}

type CreateValues = {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  role: 'admin' | 'fleet_manager' | 'driver';
  first_name?: string;
  last_name?: string;
};
type EditValues = {
  email?: string;
  role: 'admin' | 'fleet_manager' | 'driver';
  first_name?: string;
  last_name?: string;
  is_active: boolean;
};

export function AdminUserFormPage() {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const isEditing = Boolean(params.id);
  const userId = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const userQuery = useAdminUser(userId);
  const createMutation = useCreateAdminUser();
  const updateMutation = useUpdateAdminUser(userId ?? -1);

  const { createSchema, editSchema } = useSchemas(t);

  const createForm = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      username: '',
      email: '',
      password: '',
      password_confirm: '',
      role: 'driver',
      first_name: '',
      last_name: '',
    },
  });

  const editForm = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: userQuery.data
      ? {
          email: userQuery.data.email,
          role: userQuery.data.role,
          first_name: userQuery.data.first_name,
          last_name: userQuery.data.last_name,
          is_active: userQuery.data.is_active,
        }
      : undefined,
    defaultValues: { email: '', role: 'driver', first_name: '', last_name: '', is_active: true },
  });

  if (isEditing && userQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t('adminForm.loadingUser')}</p>;
  }
  if (isEditing && userQuery.isError) {
    return <ErrorState onRetry={() => void userQuery.refetch()} title={t('adminForm.unableToLoad')} />;
  }

  async function onCreate(values: CreateValues) {
    try {
      await createMutation.mutateAsync(values);
      toast({ title: t('adminForm.userCreated'), variant: 'success' });
      navigate('/admin/users');
    } catch (error) {
      toast({
        title: t('adminForm.couldNotCreate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  async function onUpdate(values: EditValues) {
    try {
      await updateMutation.mutateAsync(values);
      toast({ title: t('adminForm.userUpdated'), variant: 'success' });
      navigate('/admin/users');
    } catch (error) {
      toast({
        title: t('adminForm.couldNotUpdate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/admin/users">
            <ArrowLeft className="size-3.5" />
            {t('adminForm.backToUsers')}
          </Link>
        </Button>
        <PageHeader
          title={isEditing ? t('adminForm.editUser') : t('adminForm.newUser')}
          description={t('adminForm.sectionNote')}
        />
      </div>

      <Card className="max-w-xl">
        <CardContent className="pt-5">
          {isEditing ? (
            <form onSubmit={editForm.handleSubmit(onUpdate)} className="space-y-5" noValidate>
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="first_name">{t('register.firstName')}</Label>
                  <Input id="first_name" {...editForm.register('first_name')} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="last_name">{t('register.lastName')}</Label>
                  <Input id="last_name" {...editForm.register('last_name')} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="email">{t('common.email')}</Label>
                <Input id="email" type="email" {...editForm.register('email')} />
                {editForm.formState.errors.email && (
                  <p className="text-xs text-destructive">{editForm.formState.errors.email.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label>{t('common.role')}</Label>
                <Controller
                  control={editForm.control}
                  name="role"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.values(ROLES).map((role) => (
                          <SelectItem key={role} value={role}>
                            {t(`role.${role}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
              <div className="flex items-center justify-between rounded-md border border-input px-3 py-2">
                <Label htmlFor="is_active" className="cursor-pointer">
                  {t('adminForm.accountActive')}
                </Label>
                <Controller
                  control={editForm.control}
                  name="is_active"
                  render={({ field }) => (
                    <Switch id="is_active" checked={field.value} onCheckedChange={field.onChange} />
                  )}
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => navigate('/admin/users')}>
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={editForm.formState.isSubmitting}>
                  {editForm.formState.isSubmitting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  {t('adminForm.saveChanges')}
                </Button>
              </div>
            </form>
          ) : (
            <form onSubmit={createForm.handleSubmit(onCreate)} className="space-y-5" noValidate>
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="username">{t('login.username')}</Label>
                  <Input id="username" {...createForm.register('username')} />
                  {createForm.formState.errors.username && (
                    <p className="text-xs text-destructive">{createForm.formState.errors.username.message}</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="email">{t('common.email')}</Label>
                  <Input id="email" type="email" {...createForm.register('email')} />
                  {createForm.formState.errors.email && (
                    <p className="text-xs text-destructive">{createForm.formState.errors.email.message}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="first_name">{t('register.firstName')}</Label>
                  <Input id="first_name" {...createForm.register('first_name')} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="last_name">{t('register.lastName')}</Label>
                  <Input id="last_name" {...createForm.register('last_name')} />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label>{t('common.role')}</Label>
                <Controller
                  control={createForm.control}
                  name="role"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.values(ROLES).map((role) => (
                          <SelectItem key={role} value={role}>
                            {t(`role.${role}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="password">{t('login.password')}</Label>
                  <PasswordInput id="password" {...createForm.register('password')} />
                  {createForm.formState.errors.password && (
                    <p className="text-xs text-destructive">{createForm.formState.errors.password.message}</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password_confirm">{t('register.confirmPassword')}</Label>
                  <PasswordInput id="password_confirm" {...createForm.register('password_confirm')} />
                  {createForm.formState.errors.password_confirm && (
                    <p className="text-xs text-destructive">
                      {createForm.formState.errors.password_confirm.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => navigate('/admin/users')}>
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={createForm.formState.isSubmitting}>
                  {createForm.formState.isSubmitting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  {t('adminForm.createUser')}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
