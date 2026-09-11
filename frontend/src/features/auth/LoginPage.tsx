import * as React from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion } from 'framer-motion';
import { Activity, Eye, EyeOff, Loader2, Lock, ShieldCheck, Siren, Truck, User } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { Autoplay, Pagination } from 'swiper/modules';
import { Swiper, SwiperSlide } from 'swiper/react';
import { z } from 'zod';

import { useLanguage } from '@/app/LanguageContext';
import { LanguageToggle } from '@/components/shared/LanguageToggle';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { resolveLoginRedirect } from '@/constants/routeAccess';
import { ApiError } from '@/types/common';

import { useAuth } from './AuthContext';

import 'swiper/css';
import 'swiper/css/pagination';

function useLoginSchema() {
  const { t } = useLanguage();
  return z.object({
    username: z.string().min(1, t('login.errorUsernameRequired')),
    password: z.string().min(1, t('login.errorPasswordRequired')),
  });
}

type LoginFormValues = { username: string; password: string };

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { t, dir } = useLanguage();
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [showPassword, setShowPassword] = React.useState(false);

  const loginSchema = useLoginSchema();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  const requestedFrom = (location.state as { from?: string } | null)?.from;

  const slides = [
    { icon: Truck, title: t('login.slide1Title'), desc: t('login.slide1Desc') },
    { icon: Activity, title: t('login.slide2Title'), desc: t('login.slide2Desc') },
    { icon: Siren, title: t('login.slide3Title'), desc: t('login.slide3Desc') },
  ];

  async function onSubmit(values: LoginFormValues) {
    setServerError(null);
    try {
      const sessionUser = await login(values);
      const redirectTo = resolveLoginRedirect(sessionUser.role, requestedFrom);
      navigate(redirectTo, { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setServerError(ApiError.extractMessage(error.body) ?? t('login.errorInvalid'));
      } else {
        setServerError(t('login.errorNetwork'));
      }
    }
  }

  return (
    <div className="grid min-h-dvh bg-background lg:grid-cols-2">
      {/* Branding / carousel panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-primary via-primary to-indigo-800 p-10 text-primary-foreground lg:flex">
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.12),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(255,255,255,0.10),transparent_40%)]"
        />

        <div className="relative z-10 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-white/15 backdrop-blur">
            <Truck className="size-5" />
          </div>
          <span className="text-lg font-bold">{t('app.name')}</span>
        </div>

        <div className="relative z-10" dir={dir}>
          <Swiper
            key={dir}
            modules={[Autoplay, Pagination]}
            autoplay={{ delay: 4500, disableOnInteraction: false }}
            pagination={{ clickable: true }}
            loop
            className="pb-10"
          >
            {slides.map((slide) => (
              <SwiperSlide key={slide.title}>
                <div className="flex size-16 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
                  <slide.icon className="size-8" />
                </div>
                <h2 className="mt-6 text-2xl font-bold leading-snug">{slide.title}</h2>
                <p className="mt-3 max-w-md text-primary-foreground/80">{slide.desc}</p>
              </SwiperSlide>
            ))}
          </Swiper>
        </div>

        <div className="relative z-10 flex items-center gap-2 text-sm text-primary-foreground/70">
          <ShieldCheck className="size-4 shrink-0" />
          {t('login.secureAuth')}
        </div>
      </div>

      {/* Form panel */}
      <div className="relative flex items-center justify-center p-6 sm:p-10">
        <div className="absolute end-4 top-4 flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 flex flex-col items-center gap-2 text-center lg:hidden">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <Truck className="size-6" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">{t('app.name')}</h1>
          </div>

          <div className="mb-8 space-y-1.5 text-center">
            <h1 className="hidden text-2xl font-bold tracking-tight lg:block">{t('login.welcomeBack')}</h1>
            <p className="text-sm text-muted-foreground">{t('login.welcomeBackDesc')}</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="username">{t('login.username')}</Label>
              <div className="relative">
                <User className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="username"
                  autoFocus
                  autoComplete="username"
                  className="ps-9"
                  placeholder={t('login.usernamePlaceholder')}
                  {...register('username')}
                />
              </div>
              {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">{t('login.password')}</Label>
              <div className="relative">
                <Lock className="absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className="px-9"
                  placeholder="••••••••"
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
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
                  {t('login.signingIn')}
                </>
              ) : (
                t('login.signIn')
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            {t('login.noAccount')}{' '}
            <Link to="/register" className="font-medium text-primary hover:underline">
              {t('login.createDriverAccount')}
            </Link>
            .
          </p>
        </motion.div>
      </div>
    </div>
  );
}
