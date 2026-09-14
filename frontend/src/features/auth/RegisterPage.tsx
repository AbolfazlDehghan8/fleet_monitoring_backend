import * as React from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion } from 'framer-motion';
import { CheckCircle2, Loader2, Mail, Truck, User } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { authApi } from '@/api/auth';
import { LanguageToggle } from '@/components/shared/LanguageToggle';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PasswordInput } from '@/components/ui/password-input';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import { ApiError } from '@/types/common';

function useRegisterSchema() {
  const { t } = useLanguage();
  return z
    .object({
      username: z.string().min(1, t('login.errorUsernameRequired')).max(150, t('validation.maxLength', { max: 150 })),
      email: z.string().min(1, t('register.errorEmailRequired')).email(t('register.errorEmailInvalid')),
      first_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
      last_name: z.string().max(150, t('validation.maxLength', { max: 150 })).optional().or(z.literal('')),
      password: z.string().min(8, t('register.errorPasswordMin')),
      password_confirm: z.string().min(8, t('register.errorPasswordMin')),
    })
    .refine((data) => data.password === data.password_confirm, {
      message: t('register.errorPasswordMismatch'),
      path: ['password_confirm'],
    });
}

type RegisterFormValues = {
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  password: string;
  password_confirm: string;
};

export function RegisterPage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [done, setDone] = React.useState(false);

  const registerSchema = useRegisterSchema();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({ resolver: zodResolver(registerSchema) });

  async function onSubmit(values: RegisterFormValues) {
    setServerError(null);
    try {
      await authApi.register(values);
      setDone(true);
    } catch (error) {
      if (error instanceof ApiError) {
        setServerError(getApiErrorMessage(error.body, t) ?? t('register.errorCreate'));
      } else {
        setServerError(t('login.errorNetwork'));
      }
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-background px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,hsl(var(--primary)/0.12),transparent_45%),radial-gradient(circle_at_80%_70%,hsl(var(--primary)/0.10),transparent_40%)]"
      />

      <div className="absolute end-4 top-4 flex items-center gap-1">
        <LanguageToggle />
        <ThemeToggle />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="relative w-full max-w-sm"
      >
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Truck className="size-6" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight">{t('app.name')}</h1>
          <p className="text-sm text-muted-foreground">{t('register.title')}</p>
        </div>

        <Card className="glass shadow-lg">
          {done ? (
            <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
              <CheckCircle2 className="size-10 text-success" />
              <div className="space-y-1">
                <p className="text-sm font-medium">{t('register.accountCreated')}</p>
                <p className="text-sm text-muted-foreground">{t('register.canSignInNow')}</p>
              </div>
              <Button className="mt-2 w-full" onClick={() => navigate('/login')}>
                {t('register.goToSignIn')}
              </Button>
            </CardContent>
          ) : (
            <>
              <CardHeader>
                <CardTitle className="text-foreground">{t('register.createYourAccount')}</CardTitle>
                <CardDescription>{t('register.notice')}</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
                  <div className="space-y-1.5">
                    <Label htmlFor="username">{t('login.username')}</Label>
                    <div className="relative">
                      <User className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="username"
                        autoComplete="username"
                        className="ps-9"
                        placeholder={t('login.usernamePlaceholder')}
                        {...register('username')}
                      />
                    </div>
                    {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="email">{t('common.email')}</Label>
                    <div className="relative">
                      <Mail className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="email"
                        type="email"
                        autoComplete="email"
                        className="ps-9"
                        placeholder={t('register.emailPlaceholder')}
                        {...register('email')}
                      />
                    </div>
                    {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="first_name">{t('register.firstName')}</Label>
                      <Input id="first_name" autoComplete="given-name" {...register('first_name')} />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="last_name">{t('register.lastName')}</Label>
                      <Input id="last_name" autoComplete="family-name" {...register('last_name')} />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="password">{t('login.password')}</Label>
                    <PasswordInput
                      id="password"
                      autoComplete="new-password"
                      placeholder="••••••••"
                      {...register('password')}
                    />
                    {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="password_confirm">{t('register.confirmPassword')}</Label>
                    <PasswordInput
                      id="password_confirm"
                      autoComplete="new-password"
                      placeholder="••••••••"
                      {...register('password_confirm')}
                    />
                    {errors.password_confirm && (
                      <p className="text-xs text-destructive">{errors.password_confirm.message}</p>
                    )}
                  </div>

                  {serverError && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                      {serverError}
                    </div>
                  )}

                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        {t('register.submitting')}
                      </>
                    ) : (
                      t('register.submit')
                    )}
                  </Button>
                </form>
              </CardContent>
            </>
          )}
        </Card>

        {!done && (
          <p className="mt-6 text-center text-xs text-muted-foreground">
            {t('register.haveAccount')}{' '}
            <Link to="/login" className="font-medium text-primary hover:underline">
              {t('register.signIn')}
            </Link>
          </p>
        )}
      </motion.div>
    </div>
  );
}
