// "Report a problem" dialog (problem_reports_bridge.md §2/B-12): one free-text
// field, send/cancel — no draft state, no attachments. The backend assembles the
// evidence bundle; the browser contributes ui_evidence at send time.
import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { fileProblemReport } from '../hooks/useApi';
import { useLogStore } from '../stores/useLogStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

type Phase = 'edit' | 'sending' | 'done' | 'error';

export function ReportProblemDialog({ open, onClose }: Props) {
  const location = useLocation();
  const addLog = useLogStore((s) => s.addLog);
  const [text, setText] = useState('');
  const [phase, setPhase] = useState<Phase>('edit');
  const [message, setMessage] = useState('');

  if (!open) return null;

  // Page context (B-1): the entity the user was looking at anchors the evidence scoping.
  const entityMatch = location.pathname.match(/^\/(?:devices|scenario)\/([^/]+)/);
  const entityId = entityMatch ? entityMatch[1] : null;

  const close = () => {
    setText('');
    setPhase('edit');
    setMessage('');
    onClose();
  };

  const send = async () => {
    if (!text.trim()) return;
    setPhase('sending');
    try {
      const result = await fileProblemReport(text.trim(), entityId);
      setMessage(
        result.spooled
          ? `Сейчас нет связи — отчёт ${result.report_id} сохранён и будет отправлен позже.`
          : `Отчёт отправлен, спасибо! (${result.report_id})`
      );
      setPhase('done');
      addLog({ level: 'info', message: `Problem report ${result.report_id} ${result.spooled ? 'spooled' : 'filed'}` });
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      setMessage(
        e.response?.status === 429
          ? 'Уже отправлено несколько отчётов — попробуйте немного позже.'
          : e.response?.status === 503
            ? 'Отправка отчётов не настроена на этом сервере.'
            : `Не удалось отправить отчёт: ${e.response?.data?.detail ?? 'ошибка сети'}`
      );
      setPhase('error');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={close}>
      <div
        className="w-full max-w-md mx-4 bg-popover border border-border rounded-md shadow-lg p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold mb-2">Сообщить о проблеме</h2>
        {phase === 'done' || phase === 'error' ? (
          <>
            <p className={`text-sm mb-3 ${phase === 'error' ? 'text-amber-400' : ''}`}>{message}</p>
            <div className="flex justify-end">
              <button
                className="px-3 py-1.5 text-sm rounded-md bg-accent hover:bg-accent/80"
                onClick={close}
              >
                Закрыть
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-xs text-muted-foreground mb-2">
              Опишите проблему своими словами. Технические данные (журналы, состояния устройств)
              будут приложены автоматически.
            </p>
            <textarea
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              className="w-full px-2 py-1.5 text-sm bg-black/30 border border-white/20 rounded text-white resize-none"
              placeholder="Что не работает?"
              disabled={phase === 'sending'}
            />
            <div className="flex justify-end space-x-2 mt-3">
              <button
                className="px-3 py-1.5 text-sm rounded-md hover:bg-accent"
                onClick={close}
                disabled={phase === 'sending'}
              >
                Отмена
              </button>
              <button
                className="px-3 py-1.5 text-sm rounded-md bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50"
                onClick={() => { void send(); }}
                disabled={phase === 'sending' || !text.trim()}
              >
                {phase === 'sending' ? 'Отправка…' : 'Отправить'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
