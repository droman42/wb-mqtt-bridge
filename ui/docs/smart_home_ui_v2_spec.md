
# Smart‑Home Remote UI v2 – Technical Specification  
_Last updated: 1 June 2025_

---

## 0 · Global project metadata
| Item | Value |
|------|-------|
| **Repository** | **Reuse existing repo** – tag legacy code as `legacy-ui`, then create an orphan `main` branch (see §11). |
| **Package manager** | **pnpm ≥ 9** |
| **Node** | **20 LTS** |
| **Framework** | **React 18 + Vite 5** |
| **Styling / UI kit** | **Tailwind CSS v3 + shadcn/ui** (Heroicons 24 solid) |
| **State** | **Zustand** + `immer` |
| **HTTP caching** | TanStack Query 5 (`@tanstack/react-query`) |
| **i18n** | `react-i18next`, JSON resources via REST, fallback = English |
| **Icons** | Heroicons **plus** selected Lucide icons (MIT) |
| **Testing** | Jest + React Testing Library; Playwright (optional) |
| **Target device** | Wirenboard (ARMv7) |
| **Browser support** | Chromium ≥ 110, Firefox ≥ 110, iOS 15+ |

---

## 1 · Directory layout

```
/src
 ├─ /app                entry & root layout
 ├─ /api                REST helpers (Swagger types auto‑gen)
 ├─ /components
 │   ├─ ui/             shadcn re‑exports
 │   └─ NavCluster.tsx  ← 3×3 navigation matrix
 ├─ /pages
 │   ├─ DevicePage.tsx
 │   └─ ScenarioPage.tsx
 ├─ /prompts            ← developer‑editable prompt files
 ├─ /lib
 │   ├─ iconMap.ts
 │   ├─ PromptLoader.ts
 │   └─ registry.ts
 ├─ /hooks              custom hooks (useRoom, useLog, …)
 ├─ /stores             Zustand slices
 └─ /types              global TS types & Prompt schema
/public                 static assets
/docker
 ├─ Dockerfile
 └─ build_and_push.sh
```

---

## 2 · Data sources & REST interaction

> **Important:** The table below is **illustrative**.  
> The code‑generation pipeline **MUST** fetch and parse the live Swagger/OpenAPI JSON served at **`/docs`** (or `/openapi.json`) and generate type‑safe clients from that.  
> Any differences between the real spec and these hints must be resolved in favour of the Swagger source.

| Endpoint (hint) | Purpose |
|-----------------|---------|
| `GET /rooms` | List rooms `{ id, name }` |
| `GET /rooms/:id/devices` | Devices in room `{ id, name, type }` |
| `GET /rooms/:id/scenarios` | Scenarios in room `{ id, name }` |
| `GET /devices/:id` | Full command list & metadata |
| `GET /scenarios/:id` | Startup / shutdown sequences, roles, manual text |
| `POST /execute` | Execute command `{ id, transport, payload? }` |
| `POST /mqtt-test` | Same body; backend publishes to broker |
| `GET /i18n/:lang` | JSON i18n resources |

Swagger‑codegen (openapi‑generator‑cli) → typed client hooks → wrapped by TanStack Query for caching and automatic refetch.

---

## 3 · Prompt‑file system (developer workflow)

### 3.1 Schema (`types/Prompt.ts`)
```ts
export interface PromptPage {
  id: string;                                   // device.type or scenario.id
  title: { en: string; ru: string };

  /** 3×3 navigation matrix; omit to hide */
  menu?: {
    up: string; down: string; left: string; right: string;
    ok: string;
    aux1: string; aux2: string; aux3: string; aux4: string;
  };

  /** Range sliders */
  sliders?: Array<{
    id: string;
    min: number; max: number; step?: number;
    icon?: string;            // Heroicon or "lucide:<name>"
    ticks?: number[];
  }>;

  /** Pointer pad */
  pointer?: {
    mode: 'relative' | 'absolute';
    sensitivity?: number;     // default = 1
    hintIcon?: string | false;
  };

  /** Plain buttons */
  buttons?: Array<{
    id: string;
    icon?: string;
    label?: { en: string; ru: string };
    holdable?: boolean;
  }>;
}
```

### 3.2 Automatic registry
```ts
export const promptRegistry = Object.fromEntries(
  Object.entries(
    import.meta.glob<true, string, { default: PromptPage }>(
      '/src/prompts/**/*.prompt.{ts,js,json,y?(a)ml}', { eager: true }
    )
  ).map(([path, mod]) => [mod.default.id, mod.default])
);
```

### 3.3 Scaffold helper
```bash
pnpm dlx hygen prompt new --name sony_bravia
```

---

## 4 · Routing

| URL | View |
|-----|------|
| `/` | Redirect to first room |
| `/room/:roomId` | Room dashboard – user picks device or scenario |
| `/device/:deviceId` | `<DevicePage>` (uses prompt + REST) |
| `/scenario/:scenarioId` | `<ScenarioPage>` |

Selectors in top navbar (Room · Device · Scenario) update the path via React Router v6.

---

## 5 · Core components

| Component | Description |
|-----------|-------------|
| **NavCluster** | 3 × 3 matrix: corners = Aux1‑4, edges = arrows, center = OK. |
| **SliderControl** | Range command with live value badge; debounced send on drag‑end. |
| **PointerPad** | Touch/mouse pad; emits relative or absolute gestures. |
| **LogPanel** | Docked footer; shows timestamp, commandId, path, payload, HTTP status, slider value. |
| **PromptedPage** | Renders menu ▸ buttons ▸ pointer (order: **sliders → nav → pointer**). |

---

## 6 · Icon resolution

`lib/iconMap.ts`
```ts
import * as H from '@heroicons/react/24/solid';
import * as L from 'lucide-react';

export function resolveIcon(token: string) {
  if (token.startsWith('lucide:')) return (L as any)[token.slice(7)];
  return (H as any)[token] ?? H.QuestionMarkCircleIcon;
}
```

Default command → icon map included; prompt files may override.

---

## 7 · State & logs

### Zustand slices
| Slice | Keys | Notes |
|-------|------|-------|
| `useRoomStore` | `roomId`, `deviceId`, `scenarioId` | persisted via `sessionStorage` |
| `useLogStore` | `entries: LogEntry[]` | `push`, `clear` |
| `useSettingsStore` | `theme`, `language` | theme = `'light'|'dark'|'auto'` |

### LogEntry
```ts
{
  ts: string;               // ISO‑8601
  commandId: string;
  path: string;             // REST URL or mqtt‑test URL
  transport: 'api'|'mqtt';
  payload?: any;
  status: number;           // HTTP 2xx, 4xx…
  value?: number;           // for sliders
}
```

No persistence beyond page reload.

---

## 8 · Internationalisation
* Load browser language + `en` fallback from `/i18n/:lang`.  
* `dir="auto"` on `<body>`; no RTL translations currently required.

---

## 9 · Accessibility / shortcuts
* All interactive elements use shadcn `<Button>` with `aria-label`.  
* Keyboard: arrows / Enter / Esc map to NavCluster; `[` / `]` → volume slider ±10; `/` focuses Device dropdown.

---

## 10 · Build & deploy

### Dockerfile
```Dockerfile
# ── build ─────────────────────────────────────────
FROM --platform=linux/arm/v7 node:20-alpine AS build
WORKDIR /app
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm run build          # → dist/

# ── runtime ───────────────────────────────────────
FROM --platform=linux/arm/v7 nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx","-g","daemon off;"]
"
```

### Push script (`/docker/build_and_push.sh`)
```bash
#!/usr/bin/env bash
set -e
IMG=wb-remote-ui:latest
docker build -f docker/Dockerfile -t $IMG .
docker save $IMG | gzip > ui.tar.gz
scp ui.tar.gz root@wirenboard:/tmp/
ssh root@wirenboard "docker load < /tmp/ui.tar.gz &&
  docker stop ui 2>/dev/null || true &&
  docker rm   ui 2>/dev/null || true &&
  docker run -d --name ui -p 80:80 $IMG &&
  rm /tmp/ui.tar.gz"
```

---

## 11 · Repository reset (one‑time)

```bash
git tag legacy-ui HEAD
git checkout --orphan clean-slate
git rm -rf .
echo "node_modules\ndist\n.env" > .gitignore
git add .gitignore
git commit -m "Start v2 UI (empty)"
git branch -M clean-slate main
git push -f origin main
git push origin legacy-ui
```

---

## 12 · Non‑functional targets
* **Initial bundle ≤ 300 kB** (gzipped).  
* **Time‑to‑interactive ≤ 100 ms** over LAN on Wirenboard.  
* **Offline** support not required.  
* **Logging** is memory‑only.

---

## 13 · Deliverables for code‑generation agent
1. Vite + Tailwind scaffold with structure above.  
2. Swagger‑driven typed API client hooked to TanStack Query.  
3. Zustand stores & LogPanel.  
4. Prompt discovery & example prompts (`apple_tv`, `lg_tv`, `movie_night`).  
5. CLI scaffold command `pnpm run new:prompt <id>`.  
6. NavCluster, SliderControl, PointerPad components with unit tests.  
7. Working Docker image deployable via `build_and_push.sh`.

---

**End of specification.**
