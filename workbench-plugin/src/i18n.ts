/* Plugin-local i18n (HK-11: i18n is deliberately NOT a shared singleton — each plugin
   bundles its own; the shell provides the active locale through PageProps). The bridge
   plugin's chrome vocabulary is small enough for a typed message table — no i18n
   library needed. Device-sourced strings (localized names in configs/catalog) keep
   their own locale sets and are resolved per-value via pickName(). */

import type { Locale } from 'locveil-workbench/contract';

export interface Msg {
  ru: string;
  en: string;
}

export function t(locale: Locale, m: Msg): string {
  return locale === 'ru' ? m.ru : m.en;
}

/** Resolve a device/room localized-names map ({ru: …, en: …, de: …}) for the UI locale. */
export function pickName(
  locale: Locale,
  names: Record<string, string> | undefined,
  fallback: string
): string {
  if (!names) return fallback;
  return names[locale] ?? names.en ?? names.ru ?? Object.values(names)[0] ?? fallback;
}
