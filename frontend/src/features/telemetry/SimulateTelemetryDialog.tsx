import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, Radio } from 'lucide-react';
import * as React from 'react';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import type { TranslationKey } from '@/i18n/translations';
import { ApiError } from '@/types/common';
import type { Vehicle } from '@/types/vehicles';

import { useIngestTelemetry } from './hooks';

function useReadingSchema(t: (key: TranslationKey) => string) {
  return z.object({
    vehicle_id: z.string().min(1, t('telemetry.selectVehicleErr')),
    obu_serial: z.string().min(1, t('telemetry.obuSerialErr')),
    speed: z.coerce.number().min(0),
    engine_temperature: z.coerce.number(),
    battery_voltage: z.coerce.number().min(0).max(50),
    fuel_level: z.coerce.number().min(0).max(100),
    latitude: z.coerce.number().min(-90).max(90),
    longitude: z.coerce.number().min(-180).max(180),
    odometer: z.coerce.number().min(0),
  });
}

type ReadingValues = {
  vehicle_id: string;
  obu_serial: string;
  speed: number;
  engine_temperature: number;
  battery_voltage: number;
  fuel_level: number;
  latitude: number;
  longitude: number;
  odometer: number;
};

interface SimulateTelemetryDialogProps {
  vehicles: Vehicle[];
  defaultVehicleId?: string;
}

/**
 * Lets an admin or fleet manager POST a single packet to
 * `/api/v1/telemetry/` — the same endpoint a real OBU device uses — so the
 * ingestion → RabbitMQ → Celery → rule evaluation → alert pipeline can be
 * exercised by hand (e.g. submit speed=140 against a "speed > 120" rule
 * and confirm an alert appears).
 */
export function SimulateTelemetryDialog({ vehicles, defaultVehicleId }: SimulateTelemetryDialogProps) {
  const { t } = useLanguage();
  const [open, setOpen] = React.useState(false);
  const ingestMutation = useIngestTelemetry();
  const readingSchema = useReadingSchema(t);

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ReadingValues>({
    resolver: zodResolver(readingSchema),
    defaultValues: {
      vehicle_id: defaultVehicleId ?? '',
      obu_serial: '',
      speed: 60,
      engine_temperature: 90,
      battery_voltage: 12.6,
      fuel_level: 75,
      latitude: 35.6892,
      longitude: 51.389,
      odometer: 10000,
    },
  });

  const selectedVehicleId = watch('vehicle_id');

  React.useEffect(() => {
    const vehicle = vehicles.find((v) => v.vehicle_id === selectedVehicleId);
    if (vehicle?.obu?.serial_number) {
      setValue('obu_serial', vehicle.obu.serial_number);
    }
  }, [selectedVehicleId, vehicles, setValue]);

  async function onSubmit(values: ReadingValues) {
    try {
      await ingestMutation.mutateAsync({ ...values, timestamp: new Date().toISOString() });
      toast({
        title: t('telemetry.readingSubmitted'),
        description: t('telemetry.readingQueued'),
        variant: 'success',
      });
      setOpen(false);
    } catch (error) {
      toast({
        title: t('telemetry.couldNotSubmit'),
        description: error instanceof ApiError ? ApiError.extractMessage(error.body) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <Radio className="size-4" />
          {t('telemetry.simulateReading')}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('telemetry.submitReadingTitle')}</DialogTitle>
          <DialogDescription>{t('telemetry.submitReadingDesc')}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label>{t('telemetry.vehicle')}</Label>
            <Controller
              control={control}
              name="vehicle_id"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('telemetry.selectVehicle')} />
                  </SelectTrigger>
                  <SelectContent>
                    {vehicles.map((v) => (
                      <SelectItem key={v.id} value={v.vehicle_id}>
                        {v.vehicle_id} · {v.make} {v.model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.vehicle_id && <p className="text-xs text-destructive">{errors.vehicle_id.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="obu_serial">{t('telemetry.obuSerial')}</Label>
            <Input id="obu_serial" {...register('obu_serial')} />
            {errors.obu_serial && <p className="text-xs text-destructive">{errors.obu_serial.message}</p>}
            <p className="text-xs text-muted-foreground">{t('telemetry.obuAutoFilled')}</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="speed">{t('telemetry.speedUnit')}</Label>
              <Input id="speed" type="number" step="any" {...register('speed')} />
              {errors.speed && <p className="text-xs text-destructive">{errors.speed.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="engine_temperature">{t('telemetry.engineTempUnit')}</Label>
              <Input id="engine_temperature" type="number" step="any" {...register('engine_temperature')} />
              {errors.engine_temperature && (
                <p className="text-xs text-destructive">{errors.engine_temperature.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="battery_voltage">{t('telemetry.batteryUnit')}</Label>
              <Input id="battery_voltage" type="number" step="any" {...register('battery_voltage')} />
              {errors.battery_voltage && (
                <p className="text-xs text-destructive">{errors.battery_voltage.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fuel_level">{t('telemetry.fuelLevelUnit')}</Label>
              <Input id="fuel_level" type="number" step="any" {...register('fuel_level')} />
              {errors.fuel_level && <p className="text-xs text-destructive">{errors.fuel_level.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="latitude">{t('telemetry.latitude')}</Label>
              <Input id="latitude" type="number" step="any" {...register('latitude')} />
              {errors.latitude && <p className="text-xs text-destructive">{errors.latitude.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="longitude">{t('telemetry.longitude')}</Label>
              <Input id="longitude" type="number" step="any" {...register('longitude')} />
              {errors.longitude && <p className="text-xs text-destructive">{errors.longitude.message}</p>}
            </div>
            <div className="col-span-2 space-y-1.5">
              <Label htmlFor="odometer">{t('telemetry.odometerUnit')}</Label>
              <Input id="odometer" type="number" step="any" {...register('odometer')} />
              {errors.odometer && <p className="text-xs text-destructive">{errors.odometer.message}</p>}
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Radio className="size-4" />}
              {t('telemetry.submitReading')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
