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
import { toast } from '@/components/ui/use-toast';
import {
  useCreateDriver,
  useDriver,
  useLinkableDriverUsers,
  useUpdateDriver,
} from '@/features/vehicles/hooks';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import { IRAN_LICENSE_NUMBER_REGEX, IRAN_MOBILE_REGEX } from '@/utils/iranValidators';

function useSchemas(t: (key: TranslationKey, vars?: Record<string, string | number>) => string) {
  const phoneField = z
    .string()
    .min(1, t('driverForm.phoneRequired'))
    .max(11, t('driverForm.phoneNumberErr'))
    .regex(IRAN_MOBILE_REGEX, t('driverForm.phoneNumberErr'));

  const licenseField = z
    .string()
    .min(1, t('driverForm.licenseRequired'))
    .regex(IRAN_LICENSE_NUMBER_REGEX, t('driverForm.licenseNumberErr'));

  const createSchema = z.object({
    user: z.string().min(1, t('driverForm.userRequired')),
    license_number: licenseField,
    phone_number: phoneField,
  });

  const editSchema = z.object({
    license_number: licenseField,
    phone_number: phoneField,
    is_active: z.boolean(),
  });

  return { createSchema, editSchema };
}

type CreateValues = { user: string; license_number: string; phone_number: string };
type EditValues = { license_number: string; phone_number: string; is_active: boolean };

export function DriverFormPage() {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const isEditing = Boolean(params.id);
  const driverId = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const driverQuery = useDriver(driverId);
  const createMutation = useCreateDriver();
  const updateMutation = useUpdateDriver(driverId ?? -1);
  const { createSchema, editSchema } = useSchemas(t);

  // Available to Admin AND Fleet Manager alike — a narrow, read-only lookup of
  // driver-role users who don't have a driver profile yet (no numeric-ID guessing,
  // no need to ask an admin per profile).
  const linkableUsersQuery = useLinkableDriverUsers();
  const driverUsers = (linkableUsersQuery.data ?? []).map((u) => ({
    id: u.id,
    label: u.username,
  }));

  const createForm = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { user: '', license_number: '', phone_number: '' },
  });

  const editForm = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    values: driverQuery.data
      ? {
          license_number: driverQuery.data.license_number,
          phone_number: driverQuery.data.phone_number ?? '',
          is_active: driverQuery.data.is_active,
        }
      : undefined,
    defaultValues: { license_number: '', phone_number: '', is_active: true },
  });

  if (isEditing && driverQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t('driverForm.loadingDriver')}</p>;
  }
  if (isEditing && driverQuery.isError) {
    return <ErrorState onRetry={() => void driverQuery.refetch()} title={t('driverForm.unableToLoad')} />;
  }

  async function onCreate(values: CreateValues) {
    try {
      await createMutation.mutateAsync({
        user: Number(values.user),
        license_number: values.license_number,
        phone_number: values.phone_number,
      });
      toast({ title: t('driverForm.profileCreated'), variant: 'success' });
      navigate('/drivers');
    } catch (error) {
      toast({
        title: t('driverForm.couldNotCreate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  async function onUpdate(values: EditValues) {
    try {
      await updateMutation.mutateAsync(values);
      toast({ title: t('driverForm.profileUpdated'), variant: 'success' });
      navigate('/drivers');
    } catch (error) {
      toast({
        title: t('driverForm.couldNotUpdate'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/drivers">
            <ArrowLeft className="size-3.5" />
            {t('driverForm.backToDrivers')}
          </Link>
        </Button>
        <PageHeader
          title={isEditing ? t('driverForm.editProfile') : t('driverForm.newProfile')}
          description={isEditing ? t('driverForm.descEdit') : t('driverForm.descCreate')}
        />
      </div>

      <Card className="max-w-xl">
        <CardContent className="pt-5">
          {isEditing ? (
            <form onSubmit={editForm.handleSubmit(onUpdate)} className="space-y-5" noValidate>
              <div className="space-y-1.5">
                <Label htmlFor="license_number">{t('driverForm.licenseNumber')}</Label>
                <Input
                  id="license_number"
                  placeholder="1234567890"
                  maxLength={10}
                  inputMode="numeric"
                  dir="ltr"
                  {...editForm.register('license_number')}
                />
                {editForm.formState.errors.license_number && (
                  <p className="text-xs text-destructive">{editForm.formState.errors.license_number.message}</p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="phone_number">{t('driverForm.phoneNumber')}</Label>
                <Input
                  id="phone_number"
                  placeholder="09123456789"
                  maxLength={11}
                  inputMode="numeric"
                  dir="ltr"
                  {...editForm.register('phone_number')}
                />
                {editForm.formState.errors.phone_number && (
                  <p className="text-xs text-destructive">{editForm.formState.errors.phone_number.message}</p>
                )}
              </div>
              <div className="flex items-center justify-between rounded-md border border-input px-3 py-2">
                <Label htmlFor="is_active" className="cursor-pointer">
                  {t('driverForm.driverActive')}
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
                <Button type="button" variant="outline" onClick={() => navigate('/drivers')}>
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
              <div className="space-y-1.5">
                <Label>{t('driverForm.linkedUser')}</Label>
                <Controller
                  control={createForm.control}
                  name="user"
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      disabled={linkableUsersQuery.isLoading}
                    >
                      <SelectTrigger>
                        <SelectValue
                          placeholder={
                            linkableUsersQuery.isLoading
                              ? t('driverForm.loadingUsers')
                              : t('driverForm.selectDriverUser')
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {driverUsers.map((u) => (
                          <SelectItem key={u.id} value={String(u.id)}>
                            {u.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {!linkableUsersQuery.isLoading && driverUsers.length === 0 && (
                  <p className="text-xs text-muted-foreground">{t('driverForm.noLinkableUsers')}</p>
                )}
                {createForm.formState.errors.user && (
                  <p className="text-xs text-destructive">{createForm.formState.errors.user.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="license_number">{t('driverForm.licenseNumber')}</Label>
                <Input
                  id="license_number"
                  placeholder="1234567890"
                  maxLength={10}
                  inputMode="numeric"
                  dir="ltr"
                  {...createForm.register('license_number')}
                />
                {createForm.formState.errors.license_number && (
                  <p className="text-xs text-destructive">
                    {createForm.formState.errors.license_number.message}
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="phone_number">{t('driverForm.phoneNumber')}</Label>
                <Input
                  id="phone_number"
                  placeholder="09123456789"
                  maxLength={11}
                  inputMode="numeric"
                  dir="ltr"
                  {...createForm.register('phone_number')}
                />
                {createForm.formState.errors.phone_number && (
                  <p className="text-xs text-destructive">{createForm.formState.errors.phone_number.message}</p>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => navigate('/drivers')}>
                  {t('common.cancel')}
                </Button>
                <Button type="submit" disabled={createForm.formState.isSubmitting}>
                  {createForm.formState.isSubmitting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Save className="size-4" />
                  )}
                  {t('driverForm.createProfile')}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
