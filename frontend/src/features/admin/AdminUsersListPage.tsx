import * as React from 'react';
import { Pencil, Plus, ShieldCheck, Trash2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useLanguage } from '@/app/LanguageContext';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { FilterBar } from '@/components/shared/FilterBar';
import { PageHeader } from '@/components/shared/PageHeader';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { toast } from '@/components/ui/use-toast';
import { ROLES, type Role } from '@/constants/roles';
import { useAuth } from '@/features/auth/AuthContext';
import { ApiError } from '@/types/common';
import { getApiErrorMessage } from '@/i18n/apiErrors';
import type { AdminUser } from '@/types/admin';

import { useAdminUsers, useDeleteAdminUser, useUpdateAdminUser } from './hooks';

function ActiveToggle({ targetUser, disabled }: { targetUser: AdminUser; disabled?: boolean }) {
  const { t } = useLanguage();
  const updateMutation = useUpdateAdminUser(targetUser.id);

  async function handleToggle(checked: boolean) {
    try {
      await updateMutation.mutateAsync({ is_active: checked });
    } catch (error) {
      toast({
        title: t('admin.failedToUpdateUser'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  return (
    <Switch
      checked={targetUser.is_active}
      onCheckedChange={(checked) => void handleToggle(checked)}
      disabled={disabled || updateMutation.isPending}
      onClick={(e) => e.stopPropagation()}
    />
  );
}

export function AdminUsersListPage() {
  const { t } = useLanguage();
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();
  const [roleFilter, setRoleFilter] = React.useState('');
  const usersQuery = useAdminUsers(roleFilter ? (roleFilter as Role) : undefined);
  const deleteMutation = useDeleteAdminUser();

  const [search, setSearch] = React.useState('');
  const [pendingDeleteId, setPendingDeleteId] = React.useState<number | null>(null);

  const filtered = React.useMemo(() => {
    const data = usersQuery.data ?? [];
    return data.filter((u) => {
      const haystack = `${u.username} ${u.email} ${u.first_name} ${u.last_name}`.toLowerCase();
      return !search || haystack.includes(search.toLowerCase());
    });
  }, [usersQuery.data, search]);

  async function handleDelete() {
    if (pendingDeleteId === null) return;
    try {
      await deleteMutation.mutateAsync(pendingDeleteId);
      toast({ title: t('admin.userDeleted'), variant: 'success' });
      setPendingDeleteId(null);
    } catch (error) {
      toast({
        title: t('admin.failedToDeleteUser'),
        description: error instanceof ApiError ? getApiErrorMessage(error.body, t) : undefined,
        variant: 'destructive',
      });
    }
  }

  const columns: DataTableColumn<AdminUser>[] = [
    {
      id: 'username',
      header: t('admin.colUser'),
      sortAccessor: (row) => row.username,
      cell: (row) => (
        <div>
          <p className="text-sm font-medium">
            {row.first_name || row.last_name ? `${row.first_name} ${row.last_name}`.trim() : row.username}
          </p>
          <p className="text-xs text-muted-foreground">
            {row.username} · {row.email}
          </p>
        </div>
      ),
    },
    {
      id: 'role',
      header: t('admin.colRole'),
      sortAccessor: (row) => row.role,
      cell: (row) => <Badge variant="outline">{t(`role.${row.role}`)}</Badge>,
    },
    {
      id: 'is_active',
      header: t('admin.colActive'),
      sortAccessor: (row) => (row.is_active ? 1 : 0),
      cell: (row) => <ActiveToggle targetUser={row} disabled={row.id === currentUser?.id} />,
    },
    {
      id: 'created_at',
      header: t('common.created'),
      cell: (row) => (
        <span className="num-tabular text-xs text-muted-foreground">
          {new Date(row.created_at).toLocaleDateString()}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="text-muted-foreground hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/admin/users/${row.id}/edit`);
            }}
          >
            <Pencil className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="text-muted-foreground hover:text-destructive"
            disabled={row.id === currentUser?.id}
            onClick={(e) => {
              e.stopPropagation();
              setPendingDeleteId(row.id);
            }}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ),
      className: 'text-end',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('admin.usersTitle')}
        description={t('admin.usersDescription')}
        actions={
          <Button size="sm" onClick={() => navigate('/admin/users/new')}>
            <Plus className="size-4" />
            {t('admin.newUser')}
          </Button>
        }
      />

      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('admin.searchPlaceholder')}
        selects={[
          {
            key: 'role',
            label: t('admin.colRole'),
            value: roleFilter,
            onChange: setRoleFilter,
            options: Object.values(ROLES).map((role) => ({ value: role, label: t(`role.${role}`) })),
          },
        ]}
        hasActiveFilters={Boolean(search || roleFilter)}
        onClear={() => {
          setSearch('');
          setRoleFilter('');
        }}
      />

      {usersQuery.isError ? (
        <ErrorState onRetry={() => void usersQuery.refetch()} />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          getRowId={(row) => row.id}
          isLoading={usersQuery.isLoading}
          onRowClick={(row) => navigate(`/admin/users/${row.id}/edit`)}
          emptyTitle={t('admin.noUsersFound')}
          emptyDescription={t('admin.noUsersFoundDesc')}
          emptyIcon={ShieldCheck}
        />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => !open && setPendingDeleteId(null)}
        title={t('admin.deleteUserTitle')}
        description={t('admin.cannotBeUndone')}
        confirmLabel={t('common.delete')}
        destructive
        loading={deleteMutation.isPending}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
