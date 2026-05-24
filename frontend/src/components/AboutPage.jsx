import Header from "./Header";

const { useEffect } = React;

function AboutHero() {
  return (
    <section className="about-hero">
      <div className="about-wrap">
        <div className="eyebrow">О команде</div>
        <h1 className="about-display">BigPuzoTeam</h1>
        <p className="about-lede">
          Мы строим TrendWatcher — инструмент для поиска важных финтех-сигналов
          в потоке открытых публикаций.
        </p>

        <div className="about-hero-text">
          <p>
            Мы учимся в Лицее НИУ ВШЭ на направлении, где математика, инженерия
            и информатика соединяются с разработкой реальных продуктов.
            В этом проекте мы применяем то, что обычно остаётся в учебных задачах:
            работу с данными, ML-логику, backend-инфраструктуру, продуктовый анализ
            и быстрый запуск MVP.
          </p>
          <p>
            TrendWatcher помогает быстрее понять, какие публикации действительно
            важны для банка: где появился новый пользовательский сценарий,
            продуктовая механика, партнёрство, регуляторный сигнал или заметное
            изменение на рынке.
          </p>
        </div>

        <div className="about-hero-cta">
          <a className="primary-button" href="/#signals">Посмотреть демо</a>
          <a className="secondary-button" href="/#summary">Запустить анализ</a>
        </div>
      </div>
    </section>
  );
}

function StatementBlock() {
  return (
    <section className="about-statement">
      <div className="about-wrap">
        <h2 className="about-statement-line">Мы не делаем агрегатор новостей.</h2>
        <p className="about-statement-sub">
          Наша задача — отделить сигнал от шума: найти публикации, которые могут
          быть полезны продуктовой команде, объяснить их важность и собрать
          короткий дайджест с проверяемыми источниками.
        </p>
      </div>
    </section>
  );
}

function BuildBlock() {
  const cards = [
    {
      title: "Signal Detection",
      body:
        "Находим публикации, в которых есть продуктовый или рыночный смысл: новые банковские функции, UX-механики, партнёрства, регулирование и изменения пользовательских сценариев.",
    },
    {
      title: "Noise Filtering",
      body:
        "Отсекаем материалы, которые выглядят как финтех-новости, но не дают полезного вывода: пересказы без первоисточника, повторяющиеся публикации и нерелевантные упоминания.",
    },
    {
      title: "Importance Scoring",
      body:
        "Оцениваем важность сигнала по нескольким факторам: новизна, связь с банковскими продуктами, надёжность источника, подтверждение и потенциальная польза для команды.",
    },
    {
      title: "Digest Generation",
      body:
        "Формируем короткую выжимку, why now, категорию, ссылки и черновик сообщения, который можно быстро передать команде.",
    },
  ];

  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">01 · Продукт</div>
          <div>
            <h2>Что мы разрабатываем</h2>
            <div className="about-section-text">
              <p>TrendWatcher — это веб-сервис для анализа финтех-публикаций.</p>
              <p>
                Он принимает материалы из открытых источников или тестового
                набора, фильтрует нерелевантные новости, находит дубли, оценивает
                важность сигналов и превращает результат в понятную карточку для
                внутреннего пользователя.
              </p>
              <p>
                На выходе команда получает не просто список ссылок, а короткий
                разбор: что произошло, почему это важно сейчас, к какой категории
                относится сигнал и на какие источники можно опереться.
              </p>
            </div>
          </div>
        </div>

        <div className="about-card-grid about-card-grid-4">
          {cards.map((card, i) => (
            <article className="about-card" key={card.title}>
              <div className="about-card-num">{String(i + 1).padStart(2, "0")}</div>
              <h3 className="about-card-title">{card.title}</h3>
              <p className="about-card-body">{card.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function SignalCategoriesBlock() {
  const cards = [
    {
      num: "01",
      title: "Банковский продукт",
      body:
        "Новые функции, сервисы, тарифы, клиентские сценарии и продуктовые запуски банков.",
    },
    {
      num: "02",
      title: "Платёжный сервис",
      body:
        "Изменения в платежах, переводах, эквайринге, кошельках, QR-оплате, подписках и других платёжных механиках.",
    },
    {
      num: "03",
      title: "UX-механика",
      body:
        "Новые способы взаимодействия с пользователем: онбординг, персонализация, подсказки, упрощение сценариев, изменения в интерфейсах.",
    },
    {
      num: "04",
      title: "Партнёрство",
      body:
        "Совместные запуски банков, финтех-компаний, ритейла, маркетплейсов и технологических сервисов.",
    },
    {
      num: "05",
      title: "Регулирование",
      body:
        "Новости, связанные с требованиями ЦБ, законами, ограничениями, комплаенсом и изменениями правил для финансового рынка.",
    },
    {
      num: "06",
      title: "Рынок",
      body:
        "Заметные рыночные тренды, действия конкурентов, изменения пользовательского поведения и новые направления в финтехе.",
    },
  ];

  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">02 · Сигналы</div>
          <div>
            <h2>Какие сигналы мы ищем</h2>
            <div className="about-section-text">
              <p>
                TrendWatcher не пытается охватить все финансовые новости. Мы
                фокусируемся на сигналах, которые могут быть полезны продуктовой
                команде, аналитикам или команде конкурентного анализа.
              </p>
            </div>
          </div>
        </div>

        <div className="about-card-grid about-card-grid-signals">
          {cards.map((card) => (
            <article className="about-card" key={card.title}>
              <div className="about-card-num">{card.num}</div>
              <h3 className="about-card-title">{card.title}</h3>
              <p className="about-card-body">{card.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function MetricsBlock() {
  const metrics = [
    { value: "3", label: "человека в команде" },
    { value: "1", label: "рабочий MVP" },
    {
      value: "6",
      label: "категорий сигналов",
      hint: "Продукты, платежи, UX, партнёрства, регулирование и рынок.",
    },
    {
      value: "Фокус",
      label: "на качестве отбора, а не на количестве ссылок",
      small: true,
    },
  ];

  return (
    <section className="about-section about-section-tight">
      <div className="about-wrap">
        <div className="about-metrics">
          {metrics.map((m) => (
            <div className="about-metric" key={m.label}>
              <div className={`about-metric-value ${m.small ? "is-small" : ""}`}>{m.value}</div>
              <div className="about-metric-label">{m.label}</div>
              {m.hint && <div className="about-metric-hint">{m.hint}</div>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ApproachBlock() {
  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">03 · Процесс</div>
          <div>
            <h2>Как мы работаем</h2>
            <div className="about-section-text">
              <p>Мы строим проект как небольшой продукт, а не как разовую презентацию.</p>
              <p>
                Сначала определяем пользователя и задачу. Затем собираем минимальный
                рабочий сценарий: входные материалы → фильтрация → оценка важности →
                карточка сигнала → итоговый дайджест. После этого проверяем,
                насколько результат понятен человеку, который не участвовал в разработке.
              </p>
              <p>
                Для нас важно, чтобы сервис можно было не только показать, но и
                объяснить: откуда берутся оценки, почему материал попал в дайджест
                и какие ограничения есть у текущей версии.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function TeamBlock() {
  const members = [
    {
      name: "Лыткин Владислав",
      role: "Team Lead + ML",
      initials: "ЛВ",
      body:
        "Отвечает за общее направление разработки, ML-логику и качество анализа публикаций. Работает над тем, чтобы TrendWatcher не просто пересказывал новости, а выделял сигналы, которые действительно могут быть полезны для продуктовой или аналитической команды.",
    },
    {
      name: "Александр Лычман",
      role: "Backend + DevOps",
      initials: "АЛ",
      body:
        "Отвечает за серверную часть, API, обработку данных, инфраструктуру и деплой. Его зона — чтобы сервис стабильно принимал материалы, запускал обработку и возвращал результат в понятном формате.",
    },
    {
      name: "Егор Мальцев",
      role: "Product Manager",
      initials: "ЕМ",
      body:
        "Отвечает за продуктовую логику, пользовательский сценарий и упаковку решения. Следит за тем, чтобы TrendWatcher решал конкретную задачу, был понятен жюри и выглядел как продукт, а не как набор отдельных функций.",
    },
  ];

  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">04 · Команда</div>
          <div>
            <h2>Наша команда</h2>
            <div className="about-section-text">
              <p>Мы — BigPuzoTeam, команда из Лицея НИУ ВШЭ.</p>
              <p>
                Нас объединяет интерес к инженерным продуктам, данным и задачам,
                где важно не просто написать код, а собрать работающий сценарий
                для пользователя. В TrendWatcher каждый отвечает за свою часть,
                но решения принимаются как в продуктовой команде: через задачу,
                пользу и проверку результата.
              </p>
            </div>
          </div>
        </div>

        <div className="about-card-grid about-card-grid-3">
          {members.map((m) => (
            <article className="about-member" key={m.name}>
              <div className="about-member-avatar" aria-hidden="true">{m.initials}</div>
              <div className="about-member-name">{m.name}</div>
              <div className="about-member-role">{m.role}</div>
              <p className="about-member-body">{m.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function CapabilityBlock() {
  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">05 · Контекст</div>
          <div>
            <h2>Почему мы можем это сделать</h2>
            <div className="about-section-text">
              <p>
                Мы находимся на пересечении трёх областей: математики, инженерии
                и информатики.
              </p>
              <p>
                Математика помогает формализовать оценку важности и уверенности.
                Инженерия — собрать устойчивый сценарий обработки данных.
                Информатика — превратить логику в работающий веб-сервис.
              </p>
              <p>
                Поэтому TrendWatcher для нас — это не только кейс про финтех,
                но и проверка того, как быстро небольшая команда может собрать
                полезный аналитический инструмент.
              </p>
            </div>
          </div>
        </div>

        <div className="about-pillars">
          <div className="about-pillar">
            <span className="about-pillar-mark">Математика</span>
            <p>Формализуем оценку важности и уровень уверенности модели.</p>
          </div>
          <div className="about-pillar">
            <span className="about-pillar-mark">Инженерия</span>
            <p>Собираем устойчивый сценарий обработки и доставки результата.</p>
          </div>
          <div className="about-pillar">
            <span className="about-pillar-mark">Информатика</span>
            <p>Превращаем логику в работающий веб-сервис с понятным интерфейсом.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function QualityBlock() {
  const cards = [
    {
      title: "Проверяемые источники",
      body:
        "Каждый сигнал должен иметь ссылки, по которым можно быстро проверить контекст.",
    },
    {
      title: "Объяснимая оценка",
      body:
        "Важность не должна быть «магическим числом». Пользователь видит, почему сигнал получил такую оценку.",
    },
    {
      title: "Фильтрация дублей",
      body: "Одинаковые новости и перепечатки не должны раздувать итоговый дайджест.",
    },
    {
      title: "Человеческий результат",
      body: "Итоговый текст должен быть коротким, понятным и пригодным для передачи команде.",
    },
  ];

  return (
    <section className="about-section">
      <div className="about-wrap">
        <div className="about-sec-head">
          <div className="num">06 · Качество</div>
          <div>
            <h2>Наш подход к качеству</h2>
            <div className="about-section-text">
              <p>
                В финтех-мониторинге опасно просто доверять громким заголовкам.
                Поэтому мы отдельно смотрим на источник, повторяемость новости,
                наличие первоисточника, категорию сигнала и объяснение важности.
              </p>
              <p>
                Если система не уверена в результате, это тоже должно быть видно.
                Пользователь должен понимать не только итоговую оценку, но и причину,
                по которой материал оказался в дайджесте.
              </p>
            </div>
          </div>
        </div>

        <div className="about-card-grid about-card-grid-4">
          {cards.map((card, i) => (
            <article className="about-card" key={card.title}>
              <div className="about-card-num">{String(i + 1).padStart(2, "0")}</div>
              <h3 className="about-card-title">{card.title}</h3>
              <p className="about-card-body">{card.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function FinalCTA() {
  return (
    <section className="about-final">
      <div className="about-wrap">
        <h2 className="about-final-title">
          TrendWatcher помогает быстрее перейти от потока публикаций
          к понятным продуктовым выводам.
        </h2>
        <p className="about-final-sub">
          Загрузите материалы, запустите анализ и получите короткий дайджест
          с важностью, источниками и объяснением.
        </p>
        <div className="about-final-actions">
          <a className="primary-button about-final-button" href="/#summary">
            Начать анализ
          </a>
        </div>
      </div>
    </section>
  );
}

function AboutFooter() {
  return (
    <footer className="about-footer">
      <div className="about-wrap">
        <div className="about-footer-row">
          <span className="about-footer-brand">
            <img
              src="/logo.png"
              alt=""
              className="team-fine-logo"
              width="28"
              height="28"
              onError={(e) => { e.currentTarget.style.display = "none"; }}
            />
            BigPuzoTeam · TrendWatcher
          </span>
          <span className="about-footer-meta">финтех · банк · продукт</span>
        </div>
      </div>
    </footer>
  );
}

export default function AboutPage({ authBadge }) {
  useEffect(() => {
    document.title = "BigPuzoTeam · О нас";
  }, []);

  return (
    <div className="app-shell about-shell">
      <Header authBadge={authBadge} variant="about" />

      <main className="about-main">
        <AboutHero />
        <StatementBlock />
        <BuildBlock />
        <SignalCategoriesBlock />
        <MetricsBlock />
        <ApproachBlock />
        <TeamBlock />
        <CapabilityBlock />
        <QualityBlock />
        <FinalCTA />
      </main>

      <AboutFooter />
    </div>
  );
}
