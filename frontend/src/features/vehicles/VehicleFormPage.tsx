import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, Loader2, Save } from 'lucide-react';
import * as React from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { adminUsersApi } from '@/api/admin';
import { ErrorState } from '@/components/shared/ErrorState';
import { PageHeader } from '@/components/shared/PageHeader';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import { ROLES } from '@/constants/roles';
import { VEHICLE_STATUSES } from '@/constants/statuses';
import { useAuth } from '@/features/auth/AuthContext';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';

import { useAssignableDrivers, useCreateVehicle, useUpdateVehicle, useVehicle } from './hooks';

const NONE = '__none__';

function useVehicleSchema(t: (key: TranslationKey) => string) {
  return z.object({
    vehicle_id: z.string().min(1, t('vehicleForm.vehicleIdErr')).max(50),
    license_plate: z.string().min(1, t('vehicleForm.licensePlateErr')).max(20),
    vin: z.string().max(17).optional().or(z.literal('')),
    make: z.string().max(50).optional().or(z.literal('')),
    model: z.string().max(50).optional().or(z.literal('')),
    year: z.coerce.number().int().min(1900).max(2100).optional().or(z.nan()),
    status: z.enum(['active', 'maintenance', 'inactive', 'decommissioned']),
    driver: z.string(),
    assigned_manager: z.string(),
    obu_serial_number: z.string().max(50).optional().or(z.literal('')),
    obu_firmware_version: z.string().max(20).optional().or(z.literal('')),
  });
}

type VehicleFormValues = {
  vehicle_id: string;
  license_plate: string;
  vin?: string;
  make?: string;
  model?: string;
  year?: number;
  status: 'active' | 'maintenance' | 'inactive' | 'decommissioned';
  driver: string;
  assigned_manager: string;
  obu_serial_number?: string;
  obu_firmware_version?: string;
};

export function VehicleFormPage() {
  const { t } = useLanguage();
  const params = useParams<{ id: string }>();
  const isEditing = Boolean(params.id);
  const vehicleId = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === ROLES.ADMIN;

  const vehicleQuery = useVehicle(vehicleId);
  // Not the roster (`useDrivers`) — that's scoped to "already assigned" drivers
  // only and would never show a freshly created, not-yet-assigned driver here.
  const driversQuery = useAssignableDrivers();
  const createMutation = useCreateVehicle();
  const updateMutation = useUpdateVehicle(vehicleId ?? -1);
  const vehicleSchema = useVehicleSchema(t);
  const submitLockRef = React.useRef(false);

  // Only admins can reassign a vehicle's manager, and only admins can query
  // the fleet-manager roster (see auth_module.permissions.IsAdmin).
  const [managers, setManagers] = React.useState<{ id: number; label: string }[]>([]);
  React.useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    adminUsersApi
      .list({ role: ROLES.FLEET_MANAGER })
      .then((users) => {
        if (!cancelled) {
          setManagers(users.map((u) => ({ id: u.id, label: `${u.username} (${u.email})` })));
        }
      })
      .catch(() => {
        /* non-fatal: the field just stays empty */
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<VehicleFormValues>({
    resolver: zodResolver(vehicleSchema),
    values: vehicleQuery.data
      ? {
          vehicle_id: vehicleQuery.data.vehicle_id,
          license_plate: vehicleQuery.data.license_plate,
          vin: vehicleQuery.data.vin ?? '',
          make: vehicleQuery.data.make ?? '',
          model: vehicleQuery.data.model ?? '',
          year: vehicleQuery.data.year ?? Number.NaN,
          status: vehicleQuery.data.status,
          driver: vehicleQuery.data.driver ? String(vehicleQuery.data.driver.id) : NONE,
          assigned_manager: vehicleQuery.data.assigned_manager
            ? String(vehicleQuery.data.assigned_manager)
            : NONE,
          obu_serial_number: vehicleQuery.data.obu?.serial_number ?? '',
          obu_firmware_version: vehicleQuery.data.obu?.firmware_version ?? '',
        }
      : undefined,
    defaultValues: {
      vehicle_id: '',
      license_plate: '',
      vin: '',
      make: '',
      model: '',
      year: Number.NaN,
      status: 'active',
      driver: NONE,
      assigned_manager: NONE,
      obu_serial_number: '',
      obu_firmware_version: '',
    },
  });

  if (isEditing && vehicleQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{t('vehicleForm.loadingVehicle')}</p>;
  }

  if (isEditing && vehicleQuery.isError) {
    return <ErrorState onRetry={() => void vehicleQuery.refetch()} title={t('vehicleForm.unableToLoad')} />;
  }

  async function onSubmit(values: VehicleFormValues) {
    if (submitLockRef.current) return;
    submitLockRef.current = true;

    const payload = {
      license_plate: values.license_plate,
      vin: values.vin || null,
      make: values.make || '',
      model: values.model || '',
      year: Number.isNaN(values.year) ? null : values.year,
      status: values.status,
      driver: values.driver === NONE ? null : Number(values.driver),
      ...(isAdmin ? { assigned_manager: values.assigned_manager === NONE ? null : Number(values.assigned_manager) } : {}),
      obu_serial_number: values.obu_serial_number || undefined,
      obu_firmware_version: values.obu_firmware_version || '',
    };

    try {
      if (isEditing && vehicleId !== undefined) {
        await updateMutation.mutateAsync(payload);
        toast({ title: t('vehicleForm.vehicleUpdated'), variant: 'success' });
      } else {
        await createMutation.mutateAsync({ vehicle_id: values.vehicle_id, ...payload });
        toast({ title: t('vehicleForm.vehicleCreated'), variant: 'success' });
      }
      navigate('/vehicles');
    } catch (error) {
      toast({
        title: t('vehicleForm.couldNotSave'),
        description: error instanceof ApiError ? ApiError.extractMessage(error.body) : undefined,
        variant: 'destructive',
      });
    } finally {
      submitLockRef.current = false;
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2 -ms-2 text-muted-foreground">
          <Link to="/vehicles">
            <ArrowLeft className="size-3.5" />
            {t('vehicleDetail.backToVehicles')}
          </Link>
        </Button>
        <PageHeader
          title={isEditing ? t('vehicleForm.editVehicle') : t('vehicleForm.addVehicle')}
          description={isAdmin ? t('vehicleForm.descAdmin') : t('vehicleForm.descManager')}
        />
      </div>

      <Card className="max-w-2xl">
        <CardContent className="pt-5">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="vehicle_id">{t('vehicleForm.vehicleId')}</Label>
                <Input
                  id="vehicle_id"
                  placeholder="veh_0001"
                  disabled={isEditing}
                  {...register('vehicle_id')}
                />
                {errors.vehicle_id && <p className="text-xs text-destructive">{errors.vehicle_id.message}</p>}
                {isEditing && (
                  <p className="text-xs text-muted-foreground">{t('vehicleForm.vehicleIdLocked')}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="license_plate">{t('vehicleForm.licensePlate')}</Label>
                <Input id="license_plate" placeholder="ABC-1234" {...register('license_plate')} />
                {errors.license_plate && (
                  <p className="text-xs text-destructive">{errors.license_plate.message}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="vin">{t('vehicleForm.vin')}</Label>
                <Input id="vin" placeholder="1HGCM82633A004352" {...register('vin')} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="make">{t('vehicleForm.make')}</Label>
                <Input id="make" placeholder="Ford" {...register('make')} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="model">{t('vehicleForm.model')}</Label>
                <Input id="model" placeholder="Transit" {...register('model')} />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="year">{t('vehicleForm.year')}</Label>
                <Input id="year" type="number" placeholder="2023" {...register('year')} />
              </div>
              <div className="space-y-1.5">
                <Label>{t('common.status')}</Label>
                <Controller
                  control={control}
                  name="status"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.values(VEHICLE_STATUSES).map((s) => (
                          <SelectItem key={s} value={s}>
                            {t(`vehicleStatus.${s}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>{t('vehicleForm.driver')}</Label>
                <Controller
                  control={control}
                  name="driver"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder={t('vehicleForm.unassigned')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE}>{t('vehicleForm.unassigned')}</SelectItem>
                        {(driversQuery.data ?? []).map((d) => (
                          <SelectItem key={d.id} value={String(d.id)}>
                            {d.full_name} · {d.license_number}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>

              {isAdmin && (
                <div className="space-y-1.5">
                  <Label>{t('vehicleForm.assignedManager')}</Label>
                  <Controller
                    control={control}
                    name="assigned_manager"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder={t('vehicleForm.unassigned')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={NONE}>{t('vehicleForm.unassigned')}</SelectItem>
                          {managers.map((m) => (
                            <SelectItem key={m.id} value={String(m.id)}>
                              {m.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="obu_serial_number">{t('vehicleForm.obuSerial')}</Label>
                <Input id="obu_serial_number" placeholder="OBU-2026-0001" {...register('obu_serial_number')} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="obu_firmware_version">{t('vehicleForm.obuFirmware')}</Label>
                <Input id="obu_firmware_version" placeholder="1.4.2" {...register('obu_firmware_version')} />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" disabled={isSubmitting} onClick={() => navigate('/vehicles')}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                {isEditing ? t('vehicleForm.saveChanges') : t('vehicleForm.createVehicle')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
