import { zodResolver } from '@hookform/resolvers/zod';
import { KeyRound, Loader2, Save, UserCircle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PasswordInput } from '@/components/ui/password-input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/components/ui/use-toast';
import { useAuth } from '@/features/auth/AuthContext';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import { formatDateTime } from '@/utils/formatters';

import { useChangePassword, useProfile, useUpdateProfile } from './hooks';

function useSchemas(t: (key: TranslationKey, vars?: Record<string, string | number>) => string) {
  const profileSchema = z.object({
    first_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
    last_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
    email: z.string().email(t('register.errorEmailInvalid')),
  });

  const passwordSchema = z
    .object({
      old_password: z.string().min(1, t('profile.errorCurrentRequired')),
      new_password: z.string().min(8, t('register.errorPasswordMin')),
      new_password_confirm: z.string().min(8, t('register.errorPasswordMin')),
    })
    .refine((data) => data.new_password === data.new_password_confirm, {
      message: t('register.errorPasswordMismatch'),
      path: ['new_password_confirm'],
    })
    .refine((data) => data.old_password !== data.new_password, {
      message: t('profile.errorSamePassword'),
      path: ['new_password'],
    });

  return { profileSchema, passwordSchema };
}

type ProfileValues = { first_name?: string; last_name?: string; email: string };
type PasswordValues = { old_password: string; new_password: string; new_password_confirm: string };

export function ProfilePage() {
  const { t } = useLanguage();
  const { updateUser } = useAuth();
  const profileQuery = useProfile();
  const updateProfileMutation = useUpdateProfile();
  const changePasswordMutation = useChangePassword();

  const { profileSchema, passwordSchema } = useSchemas(t);

  const profileForm = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    values: profileQuery.data
      ? {
          first_name: profileQuery.data.first_name,
          last_name: profileQuery.data.last_name,
          email: profileQuery.data.email,
        }
      : undefined,
    defaultValues: { first_name: '', last_name: '', email: '' },
  });

  const passwordForm = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { old_password: '', new_password: '', new_password_confirm: '' },
  });

  if (profileQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t('common.loading')}</p>;
  }
  if (profileQuery.isError || !profileQuery.data) {
    return <ErrorState title={t('profile.loadFailed')} onRetry={() => void profileQuery.refetch()} />;
  }

  const profile = profileQuery.data;

  async function onSaveProfile(values: ProfileValues) {
    try {
      const updated = await updateProfileMutation.mutateAsync(values);
      updateUser({
        first_name: updated.first_name,
        last_name: updated.last_name,
        email: updated.email,
      });
      toast({ title: t('profile.updated'), variant: 'success' });
    } catch (error) {
      toast({
        title: t('profile.couldNotUpdate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  async function onChangePassword(values: PasswordValues) {
    try {
      await changePasswordMutation.mutateAsync(values);
      toast({ title: t('profile.passwordChanged'), variant: 'success' });
      passwordForm.reset({ old_password: '', new_password: '', new_password_confirm: '' });
    } catch (error) {
      toast({
        title: t('profile.couldNotChangePassword'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t('profile.title')} description={t('profile.subtitle')} />

      <Card className="max-w-xl">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{profile.username}</p>
            <p className="text-xs text-muted-foreground">
              {t('profile.memberSince')} {formatDateTime(profile.created_at)}
            </p>
          </div>
          <Badge variant="outline">{t(`role.${profile.role}`)}</Badge>
        </CardContent>
      </Card>

      <Card className="max-w-xl">
        <CardContent className="pt-5">
          <Tabs defaultValue="account">
            <TabsList>
              <TabsTrigger value="account">
                <UserCircle className="size-3.5" />
                {t('profile.tabAccount')}
              </TabsTrigger>
              <TabsTrigger value="password">
                <KeyRound className="size-3.5" />
                {t('profile.tabPassword')}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="account">
              <form onSubmit={profileForm.handleSubmit(onSaveProfile)} className="space-y-5" noValidate>
                <div className="space-y-1.5">
                  <Label htmlFor="username">{t('profile.username')}</Label>
                  <Input id="username" value={profile.username} disabled />
                  <p className="text-xs text-muted-foreground">{t('profile.usernameNote')}</p>
                </div>

                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="first_name">{t('register.firstName')}</Label>
                    <Input id="first_name" {...profileForm.register('first_name')} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="last_name">{t('register.lastName')}</Label>
                    <Input id="last_name" {...profileForm.register('last_name')} />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="email">{t('common.email')}</Label>
                  <Input id="email" type="email" {...profileForm.register('email')} />
                  {profileForm.formState.errors.email && (
                    <p className="text-xs text-destructive">{profileForm.formState.errors.email.message}</p>
                  )}
                </div>

                <div className="flex justify-end pt-2">
                  <Button type="submit" disabled={profileForm.formState.isSubmitting}>
                    {profileForm.formState.isSubmitting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Save className="size-4" />
                    )}
                    {t('profile.saveChanges')}
                  </Button>
                </div>
              </form>
            </TabsContent>

            <TabsContent value="password">
              <form onSubmit={passwordForm.handleSubmit(onChangePassword)} className="space-y-5" noValidate>
                <div className="space-y-1.5">
                  <Label htmlFor="old_password">{t('profile.currentPassword')}</Label>
                  <PasswordInput id="old_password" {...passwordForm.register('old_password')} />
                  {passwordForm.formState.errors.old_password && (
                    <p className="text-xs text-destructive">
                      {passwordForm.formState.errors.old_password.message}
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="new_password">{t('profile.newPassword')}</Label>
                    <PasswordInput id="new_password" {...passwordForm.register('new_password')} />
                    {passwordForm.formState.errors.new_password && (
                      <p className="text-xs text-destructive">
                        {passwordForm.formState.errors.new_password.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="new_password_confirm">{t('profile.confirmNewPassword')}</Label>
                    <PasswordInput
                      id="new_password_confirm"
                      {...passwordForm.register('new_password_confirm')}
                    />
                    {passwordForm.formState.errors.new_password_confirm && (
                      <p className="text-xs text-destructive">
                        {passwordForm.formState.errors.new_password_confirm.message}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button type="submit" disabled={passwordForm.formState.isSubmitting}>
                    {passwordForm.formState.isSubmitting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <KeyRound className="size-4" />
                    )}
                    {t('profile.changePassword')}
                  </Button>
                </div>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
