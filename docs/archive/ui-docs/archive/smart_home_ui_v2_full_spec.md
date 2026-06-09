
# Smart‑Home Remote UI v2 – **Complete Technical Specification**  
_Last updated: 1 June 2025_

---

## 0 · Overview
A single‑page web application that renders remote‑control pages for smart‑home devices and scenarios.  
Pages are declared once via **Prompt files** that are converted at **build‑time** into React modules using a Node CLI.  
No prompt parsing occurs in the browser.

---

## 1 · Global stack
| Item | Value |
|------|-------|
| Repository | Re‑use existing repo (tag legacy as `legacy-ui`; orphan `main`) |
| Package manager | pnpm ≥ 9 |
| Node | 20 LTS |
| Framework | React 18 + Vite 5 |
| Styling / UI | Tailwind CSS v3 + shadcn/ui |
| Icons | Heroicons 24 solid + Lucide extras |
| State | Zustand + immer |
| Data fetching | TanStack Query 5 |
| i18n | react‑i18next (JSON via REST; fallback = English) |
| Testing | Jest + React‑Testing‑Library; Playwright optional |
| Target device | Wirenboard (ARMv7) |
| Browser support | Chromium ≥ 110, Firefox ≥ 110, iOS 15+ |

---

## 2 · Directory layout
```
/src
 ├─ /api                Swagger‑generated clients
 ├─ /app                entry & root layout
 ├─ /components
 │   ├─ NavCluster.tsx
 │   ├─ SliderControl.tsx
 │   ├─ PointerPad.tsx
 │   ├─ DeviceStatePanel.tsx
 │   └─ LogPanel.tsx
 ├─ /pages              ← generated React pages
 ├─ /prompts            developer prompt sources
 ├─ /scripts
 │   └─ generate-pages.mjs
 ├─ /stores             Zustand slices
 ├─ /hooks              custom hooks
 ├─ /config             runtime.ts
 └─ /types              Prompt schema
/docker
 ├─ Dockerfile
 └─ build_and_push.sh
```

---

## 3 · REST endpoints (illustrative – generator must inspect Swagger at `/docs`)
* `GET /devices/{id}/state` – returns **BaseDeviceState** (device‑specific keys).  
* Other endpoints: rooms, devices, scenarios, execute, mqtt‑test, i18n.

---

## 4 · Prompt schema (types/Prompt.ts)
```ts
export interface PromptPage {
  id: string;
  title: { en: string; ru: string };

  menu?: {
    up: string; down: string; left: string; right: string;
    ok: string;
    aux1: string; aux2: string; aux3: string; aux4: string;
  };

  sliders?: Array<{
    id: string;
    min: number; max: number; step?: number;
    icon?: string;           // Heroicon or "lucide:<name>"
    ticks?: number[];
    transport?: 'api'|'mqtt';
    payload?: Record<string, unknown>;
  }>;

  pointer?: {
    mode: 'relative'|'absolute';
    sensitivity?: number;
    transport?: 'api'|'mqtt';
    hintIcon?: string|false;
  };

  buttons?: Array<{
    id: string;
    icon?: string;
    label?: { en: string; ru: string };
    transport?: 'api'|'mqtt';
    payload?: Record<string, unknown>;
    promptForInput?: { label: { en: string; ru: string }; paramKey: string };
    holdable?: boolean;
  }>;

  hideStatePanel?: boolean;
}
```

---

## 5 · Build‑time CLI – scripts/generate-pages.mjs
1. Parse `/prompts/**/*.prompt.(yaml|ts|js)`  
2. Validate with AJV against schema.  
3. Emit React files `/pages/{id}.gen.tsx`.  
4. Update router map and manifest JSON.  
5. Run automatically in `pnpm run gen`; both dev and production builds depend on it.

---

## 6 · Runtime layout (Device or Scenario page)
```
Top Navbar (Room ▼  Device ▼  Scenario ▼)
──────────────────────────────────────────
Sliders block
3 x 3 NavCluster
PointerPad
──────────────────────────────────────────
(DeviceStatePanel slides in from right, 320 px)
──────────────────────────────────────────
LogPanel footer (collapsible)
```

---

## 7 · Components
| Component | Notes |
|-----------|-------|
| NavCluster | 3x3 matrix with aux buttons in corners. |
| SliderControl | Debounced value send. |
| PointerPad | Touch / mouse gestures. |
| DeviceStatePanel | Collapsible; polls `/devices/{id}/state` every `runtimeConfig.statePollIntervalSec` (default 5 s). |
| LogPanel | **Collapsible footer**; toggle via `useSettingsStore.logPanelOpen`. |

---

## 8 · Stores
* `useRoomStore` – selected room/device/scenario.  
* `useLogStore` – array of LogEntry objects; push/clear.  
* `useSettingsStore` – theme, language, `statePanelOpen`, **`logPanelOpen`**.

---

## 9 · Runtime config
```ts
export const runtimeConfig = {
  statePollIntervalSec: 5,
};
```

---

## 10 · Docker deployment
Multi‑stage Dockerfile (Node 20‑alpine build → Nginx‑alpine runtime).  
`build_and_push.sh` builds, saves, scps, loads, and runs container on Wirenboard.

---

## 11 · Repository reset (completed)
Tag old code `legacy-ui`; orphan new `main`.

---

## 12 · Non‑functional requirements
* Initial bundle ≤ 300 kB gz.  
* Panel collapse animation ≤ 200 ms.  
* Polling payload ≤ 5 kB; avg CPU ≤ 1 % on Wirenboard.  
* Time‑to‑interactive ≤ 100 ms on LAN.

---

## 13 · Deliverables
1. Full scaffold (Vite + Tailwind).  
2. Swagger‑generated API hooks.  
3. Zustand stores incl. collapsible LogPanel.  
4. Prompt schema & CLI generator.  
5. Example prompts (apple_tv, lg_tv, movie_night).  
6. Generated pages wired via React Router.  
7. Core components & unit tests (NavCluster, SliderControl, DeviceStatePanel, LogPanel).  
8. Dockerfile & push script.

---

**End of specification.**
