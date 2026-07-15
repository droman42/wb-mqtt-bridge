/**
 * The Bridge Workbench plugin (UI-18) — default-exports the WorkbenchPlugin the
 * shell loads at runtime (native ESM + import map, HK-11). The shell owns chrome,
 * navigation, locale and theme; design: docs/design/ui/workbench_split.md §2.
 */

import type {
  PluginStatus,
  ReportContext,
  WorkbenchPlugin,
} from 'locveil-workbench/contract';
import { TooltipProvider } from 'locveil-ui-kit';
import type { PageProps } from 'locveil-workbench/contract';
import type { ComponentType } from 'react';

import { api } from '@/api';
import VoiceReadinessPage from '@/pages/VoiceReadinessPage';
import DeviceSetupPage from '@/pages/DeviceSetupPage';
import TopologyPage from '@/pages/TopologyPage';
import './index.css';

function page(Page: ComponentType<PageProps>): ComponentType<PageProps> {
  return function BridgePage(props: PageProps) {
    return (
      <TooltipProvider delayDuration={300}>
        <Page {...props} />
      </TooltipProvider>
    );
  };
}

/** The status slot: backend reachability + device count, catalog version alongside
 *  (workbench_split.md §2.2 — light poll; an SSE upgrade is an implementation
 *  option, not a contract need). */
const status = async (): Promise<PluginStatus> => {
  try {
    const [sys, cat] = await Promise.all([api.getSystem(), api.getCatalog()]);
    const n = sys.devices?.length ?? 0;
    return {
      level: 'ok',
      text: {
        ru: `подключено · ${n} устройств · каталог ${cat.version}`,
        en: `connected · ${n} devices · catalog ${cat.version}`,
      },
    };
  } catch {
    return { level: 'error', text: { ru: 'нет связи', en: 'disconnected' } };
  }
};

/** The chrome bug button → the bridge's live pin-validated POST /reports, with the
 *  active plugin/page carried in the report's context field (§2.2). */
const reportHook = (ctx: ReportContext): void => {
  const text = window.prompt(
    ctx.locale === 'ru'
      ? 'Опишите проблему — отчёт уйдёт в общий разбор:'
      : 'Describe the problem — the report goes to triage:'
  );
  if (!text || !text.trim()) return;
  api
    .report({
      free_text: text.trim(),
      context: { source: 'workbench', plugin: ctx.pluginId, route: ctx.route },
    })
    .then(() => {
      window.alert(ctx.locale === 'ru' ? 'Отчёт отправлен.' : 'Report filed.');
    })
    .catch((e: unknown) => {
      window.alert(
        (ctx.locale === 'ru' ? 'Не удалось отправить отчёт: ' : 'Failed to file the report: ') +
          (e instanceof Error ? e.message : String(e))
      );
    });
};

const plugin: WorkbenchPlugin = {
  id: 'bridge',
  title: { ru: 'Мост', en: 'Bridge' },
  pages: () => [
    {
      route: 'voice',
      title: { ru: 'Голосовая готовность', en: 'Voice readiness' },
      render: page(VoiceReadinessPage),
    },
    {
      route: 'device-setup',
      title: { ru: 'Устройства', en: 'Device setup' },
      render: page(DeviceSetupPage),
    },
    {
      route: 'topology',
      title: { ru: 'Топология', en: 'Topology' },
      render: page(TopologyPage),
    },
  ],
  status,
  reportHook,
};

export default plugin;
