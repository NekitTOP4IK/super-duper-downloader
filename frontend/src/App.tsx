import { useCallback, useEffect, useState } from "react";
import { type Preset, api } from "./api/client";
import { Downloads } from "./components/Downloads";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { InputPanel } from "./components/InputPanel";
import { ThemePicker } from "./components/ThemePicker";
import { countFiles, isFinished, useBatches } from "./hooks/useBatches";

const TITLE = "super-duper-downloader";

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}

export function App() {
  const { views, add, remove } = useBatches();
  const [picking, setPicking] = useState(false);

  const submit = useCallback(
    async (urls: string[], preset: Preset) => {
      const created = await api.createBatch(urls, preset);
      await add(created.batch_id);
    },
    [add],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "t" && !event.ctrlKey && !event.metaKey && !event.altKey && !isTyping(event.target)) {
        event.preventDefault();
        setPicking(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const live = views.filter((view) => !isFinished(view));
  const progress = live.map(countFiles).reduce((sum, item) => ({ done: sum.done + item.done, total: sum.total + item.total }), { done: 0, total: 0 });
  useEffect(() => {
    document.title = progress.total ? `(${progress.done}/${progress.total}) ${TITLE}` : TITLE;
  }, [progress.done, progress.total]);

  return (
    <div className="page">
      <Header onOpenThemes={() => setPicking(true)} />
      <main>
        <InputPanel onSubmit={submit} />
        <Downloads views={views} onRemove={remove} />
      </main>
      <Footer />
      {picking ? <ThemePicker onClose={() => setPicking(false)} /> : null}
    </div>
  );
}
