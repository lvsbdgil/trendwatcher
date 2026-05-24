const STEPS = [
  ["Сбор публикаций", "Ссылки, текст или Firecrawl"],
  ["Очистка шума", "Убираем нерелевантные материалы"],
  ["Дедупликация", "Склеиваем дубли и пересказы"],
  ["Оценка важности", "Считаем важность по факторам"],
  ["Карточки сигналов", "Почему сейчас, выжимка и источники"],
  ["Дайджест", "Краткий вывод для команды"],
];

export default function PipelineSteps({ active, errorStep = null }) {
  return (
    <div className="pipeline" id="pipeline" aria-label="Как работает TrendWatcher">
      {STEPS.map(([title, caption], index) => {
        const step = index + 1;
        const failed = errorStep === step;
        return (
          <div
            className={`pipeline-step ${step <= active ? "is-active" : ""} ${failed ? "is-error" : ""}`}
            key={title}
          >
            <span>{failed ? "!" : step}</span>
            <div>
              <p>{title}</p>
              <small>{caption}</small>
            </div>
          </div>
        );
      })}
    </div>
  );
}
