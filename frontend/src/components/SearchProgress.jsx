const { useState, useEffect } = React;

const SEARCH_STAGES = [
  { delay: 0, text: "Поиск Firecrawl: отправляем запрос" },
  { delay: 2000, text: "Отбираем релевантные страницы" },
  { delay: 6000, text: "Загружаем содержимое публикаций" },
  { delay: 14000, text: "Передаём материалы на анализ" },
];

const CRAWL_STAGES = [
  { delay: 0, text: "Обход источника: отправляем URL в Firecrawl" },
  { delay: 2000, text: "Находим страницы внутри источника" },
  { delay: 8000, text: "Собираем содержимое публикаций" },
  { delay: 20000, text: "Готовим материалы для анализа" },
];

const ANALYZE_STAGES = [
  { delay: 0, text: "Анализируем публикации" },
  { delay: 3000, text: "Убираем шум и дубли" },
  { delay: 7000, text: "Считаем важность и уверенность" },
  { delay: 10000, text: "Формируем дайджест" },
];

export default function SearchProgress({ mode }) {
  const stages = mode === "crawl" ? CRAWL_STAGES : mode === "analyze" ? ANALYZE_STAGES : SEARCH_STAGES;
  const [stageIndex, setStageIndex] = useState(0);
  const [dots, setDots] = useState("");

  useEffect(() => {
    setStageIndex(0);
    const timers = stages.slice(1).map((s, i) =>
      setTimeout(() => setStageIndex(i + 1), s.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [mode]);

  useEffect(() => {
    const id = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 400);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="search-progress">
      <div className="sp-summary">
        Анализируем публикации: собираем источники, убираем шум, считаем важность.
      </div>
      <div className="sp-stages">
        {stages.map((s, i) => {
          const done = i < stageIndex;
          const active = i === stageIndex;
          return (
            <div key={i} className={`sp-stage${done ? " done" : active ? " active" : " pending"}`}>
              <span className="sp-icon">{done ? "✓" : active ? "›" : "·"}</span>
              <span className="sp-text">{s.text}<span className="sp-dots">{active ? dots : ""}</span></span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
