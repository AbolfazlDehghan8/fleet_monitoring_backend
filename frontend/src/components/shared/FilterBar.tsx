import { Search, X } from 'lucide-react';

import { useLanguage } from '@/app/LanguageContext';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

export interface FilterSelectConfig {
  key: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

interface FilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  selects?: FilterSelectConfig[];
  onClear?: () => void;
  hasActiveFilters?: boolean;
}

const ALL_VALUE = '__all__';

export function FilterBar({
  searchValue,
  onSearchChange,
  searchPlaceholder,
  selects = [],
  onClear,
  hasActiveFilters,
}: FilterBarProps) {
  const { t } = useLanguage();

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="relative w-full sm:max-w-xs">
        <Search className="absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={searchPlaceholder ?? t('common.search')}
          className="ps-8"
        />
      </div>

      {selects.map((select) => (
        <Select
          key={select.key}
          value={select.value || ALL_VALUE}
          onValueChange={(v) => select.onChange(v === ALL_VALUE ? '' : v)}
        >
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue placeholder={select.label} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_VALUE}>
              {t('common.all')} {select.label}
            </SelectItem>
            {select.options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ))}

      {hasActiveFilters && onClear && (
        <Button variant="ghost" size="sm" onClick={onClear} className="text-muted-foreground">
          <X className="size-3.5" />
          {t('common.filter')}
        </Button>
      )}
    </div>
  );
}
