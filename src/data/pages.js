// Texts for the static pages (#/cms/{slug}). Written for the product; legal
// pages are drafts until the product owner approves the final wording.
// Each string is { en, ru, kk }.
export const staticPages = {
  about: {
    title: { en: "About", ru: "О нас", kk: "Біз туралы" },
    lede: {
      en: "BiletFlow is a ticketing platform for events in Kazakhstan: concerts, theatre, sport, workshops and student events.",
      ru: "BiletFlow — билетная платформа для событий в Казахстане: концерты, театр, спорт, мастер-классы и студенческие мероприятия.",
      kk: "BiletFlow — Қазақстандағы іс-шараларға арналған билет платформасы: концерттер, театр, спорт, шеберханалар және студенттік іс-шаралар.",
    },
    sections: [
      {
        h: { en: "For guests", ru: "Для зрителей", kk: "Көрермендерге" },
        p: {
          en: "Find events by city, date and category, buy tickets in a few steps and keep them in your account with a QR code and a PDF copy.",
          ru: "Ищите события по городу, дате и категории, покупайте билеты в несколько шагов и храните их в кабинете с QR-кодом и PDF-копией.",
          kk: "Іс-шараларды қала, күн және санат бойынша іздеңіз, билетті бірнеше қадамда алыңыз және оны кабинетте QR-кодпен және PDF көшірмесімен сақтаңыз.",
        },
      },
      {
        h: {
          en: "For organizers",
          ru: "Для организаторов",
          kk: "Ұйымдастырушыларға",
        },
        p: {
          en: "Anyone can create an organizer profile, publish events, set ticket types and seating, run promo campaigns with QR codes and follow sales in analytics.",
          ru: "Любой может создать профиль организатора, публиковать события, настраивать типы билетов и схему зала, запускать промо-кампании с QR-кодами и следить за продажами в аналитике.",
          kk: "Кез келген адам ұйымдастырушы профилін ашып, іс-шара жариялап, билет түрлері мен зал схемасын баптап, QR-кодты промо-науқандар жүргізіп, сатылымды аналитикада бақылай алады.",
        },
      },
      {
        h: {
          en: "Free events too",
          ru: "И бесплатные события",
          kk: "Тегін іс-шаралар да",
        },
        p: {
          en: "Free registrations work the same way as paid tickets: you get a ticket with a QR code, and the organizer sees you in the attendee list.",
          ru: "Бесплатная регистрация работает так же, как платный билет: вы получаете билет с QR-кодом, а организатор видит вас в списке участников.",
          kk: "Тегін тіркелу ақылы билет сияқты жұмыс істейді: сіз QR-коды бар билет аласыз, ал ұйымдастырушы сізді қатысушылар тізімінен көреді.",
        },
      },
    ],
  },
  faq: {
    title: { en: "FAQ", ru: "Вопросы и ответы", kk: "Жиі қойылатын сұрақтар" },
    lede: {
      en: "Short answers to the questions guests ask most.",
      ru: "Короткие ответы на самые частые вопросы.",
      kk: "Жиі қойылатын сұрақтарға қысқа жауаптар.",
    },
    faq: [
      {
        q: {
          en: "How do I buy a ticket?",
          ru: "Как купить билет?",
          kk: "Билетті қалай алуға болады?",
        },
        a: {
          en: "Open the event, choose a ticket type and press Choose. Enter the attendee details, reserve the tickets and pay. Free tickets are issued right away.",
          ru: "Откройте событие, выберите тип билета и нажмите «Выбрать». Укажите данные участника, забронируйте билеты и оплатите. Бесплатные билеты выдаются сразу.",
          kk: "Іс-шараны ашып, билет түрін таңдап, «Таңдау» батырмасын басыңыз. Қатысушы деректерін енгізіп, билетті брондап, төлеңіз. Тегін билеттер бірден беріледі.",
        },
      },
      {
        q: {
          en: "Where is my ticket?",
          ru: "Где мой билет?",
          kk: "Билетім қайда?",
        },
        a: {
          en: "In your account under My tickets. Each ticket has a QR code to show at the entrance and a PDF you can download.",
          ru: "В кабинете, в разделе «Мои билеты». У каждого билета есть QR-код для входа и PDF, который можно скачать.",
          kk: "Кабинетте, «Менің билеттерім» бөлімінде. Әр билеттің кіреберіске арналған QR-коды және жүктеп алуға болатын PDF нұсқасы бар.",
        },
      },
      {
        q: {
          en: "Can I return a ticket?",
          ru: "Можно ли вернуть билет?",
          kk: "Билетті қайтаруға бола ма?",
        },
        a: {
          en: "Refunds follow the organizer's refund policy shown on the event page. To ask for a refund, open a support case from your account.",
          ru: "Возврат идёт по правилам организатора, они указаны на странице события. Чтобы оформить возврат, создайте обращение в поддержку из кабинета.",
          kk: "Қайтару ұйымдастырушының іс-шара бетінде көрсетілген ережесі бойынша жүреді. Ол үшін кабинеттен қолдауға өтініш жіберіңіз.",
        },
      },
      {
        q: {
          en: "What is a promo code?",
          ru: "Что такое промокод?",
          kk: "Промокод деген не?",
        },
        a: {
          en: "A code from the organizer that gives a discount. Enter it at checkout, or open a campaign link or QR code: the code is then applied for you.",
          ru: "Код от организатора, который даёт скидку. Введите его при оформлении или откройте ссылку или QR-код кампании: тогда код подставится сам.",
          kk: "Ұйымдастырушы берген жеңілдік коды. Оны рәсімдеу кезінде енгізіңіз немесе науқан сілтемесін не QR-кодын ашыңыз: код өзі қолданылады.",
        },
      },
      {
        q: {
          en: "Is the payment real?",
          ru: "Оплата настоящая?",
          kk: "Төлем шынайы ма?",
        },
        a: {
          en: "Not yet. Payments on BiletFlow are simulated: no real money moves, and every payment screen says so.",
          ru: "Пока нет. Оплата на BiletFlow демонстрационная: реальные деньги не списываются, и это указано на каждом экране оплаты.",
          kk: "Әзірге жоқ. BiletFlow-дағы төлем демонстрациялық: нақты ақша есептен шығарылмайды және бұл әр төлем бетінде жазылған.",
        },
      },
      {
        q: {
          en: "Something is wrong with my order",
          ru: "С заказом что-то не так",
          kk: "Тапсырысымда қате бар",
        },
        a: {
          en: "Open Support in your account, pick the order and describe the problem. You will get answers in the same conversation.",
          ru: "Откройте «Поддержку» в кабинете, выберите заказ и опишите проблему. Ответы придут в ту же переписку.",
          kk: "Кабинеттегі «Қолдау» бөлімін ашып, тапсырысты таңдап, мәселені сипаттаңыз. Жауаптар сол хат алмасуға келеді.",
        },
      },
    ],
  },
  contacts: {
    title: { en: "Contacts", ru: "Контакты", kk: "Байланыс" },
    lede: {
      en: "The fastest way to reach us is a support case: it keeps the whole conversation and the order in one place.",
      ru: "Быстрее всего связаться с нами через обращение в поддержку: вся переписка и заказ будут в одном месте.",
      kk: "Бізбен ең жылдам байланыс — қолдауға өтініш: бүкіл хат алмасу мен тапсырыс бір жерде сақталады.",
    },
    sections: [
      {
        h: { en: "Guests", ru: "Зрителям", kk: "Көрермендерге" },
        p: {
          en: "Questions about tickets, payments and refunds: Account → Support.",
          ru: "Вопросы о билетах, оплате и возвратах: Кабинет → Поддержка.",
          kk: "Билет, төлем және қайтару туралы сұрақтар: Кабинет → Қолдау.",
        },
        link: {
          to: "/account/support",
          en: "Open support",
          ru: "Открыть поддержку",
          kk: "Қолдауды ашу",
        },
      },
      {
        h: { en: "Organizers", ru: "Организаторам", kk: "Ұйымдастырушыларға" },
        p: {
          en: "Questions about events, payouts and activation: Organizer workspace → Support.",
          ru: "Вопросы о событиях, выплатах и активации: Кабинет организатора → Поддержка.",
          kk: "Іс-шара, төлемдер және белсендіру туралы сұрақтар: Ұйымдастырушы кабинеті → Қолдау.",
        },
        link: {
          to: "/organizer/support",
          en: "Organizer support",
          ru: "Поддержка организаторов",
          kk: "Ұйымдастырушы қолдауы",
        },
      },
      {
        h: {
          en: "Report an event",
          ru: "Пожаловаться на событие",
          kk: "Іс-шара туралы шағым",
        },
        p: {
          en: "If an event looks wrong or unsafe, use Report this event at the bottom of its page.",
          ru: "Если событие выглядит неправильно или небезопасно, нажмите «Пожаловаться на событие» внизу его страницы.",
          kk: "Іс-шара күмәнді не қауіпті көрінсе, оның бетінің төменгі жағындағы «Іс-шара туралы шағым» батырмасын басыңыз.",
        },
      },
    ],
  },
  agreement: {
    title: { en: "Public offer", ru: "Публичная оферта", kk: "Жария оферта" },
    draft: true,
    lede: {
      en: "Terms for buying tickets and registering for events on BiletFlow.",
      ru: "Условия покупки билетов и регистрации на события в BiletFlow.",
      kk: "BiletFlow-да билет сатып алу және іс-шараға тіркелу шарттары.",
    },
    sections: [
      {
        h: { en: "1. Who is who", ru: "1. Стороны", kk: "1. Тараптар" },
        p: {
          en: "BiletFlow provides the platform. The organizer runs the event and is responsible for it. The guest buys or registers for a ticket.",
          ru: "BiletFlow предоставляет платформу. Организатор проводит событие и отвечает за него. Зритель покупает билет или регистрируется.",
          kk: "BiletFlow платформаны ұсынады. Ұйымдастырушы іс-шараны өткізеді және оған жауап береді. Көрермен билет алады немесе тіркеледі.",
        },
      },
      {
        h: { en: "2. Ordering", ru: "2. Заказ", kk: "2. Тапсырыс" },
        p: {
          en: "A reservation holds tickets for a limited time. If it is not paid in time, it expires and the tickets go back on sale. A ticket is issued after a successful payment, or right away for a free ticket.",
          ru: "Бронь удерживает билеты ограниченное время. Если её не оплатить вовремя, она истекает, и билеты возвращаются в продажу. Билет выдаётся после успешной оплаты, бесплатный — сразу.",
          kk: "Бронь билеттерді шектеулі уақыт ұстайды. Уақытында төленбесе, ол жойылып, билеттер қайта сатылымға шығады. Билет сәтті төлемнен кейін, тегіні бірден беріледі.",
        },
      },
      {
        h: {
          en: "3. Prices and fees",
          ru: "3. Цены и сборы",
          kk: "3. Баға және алымдар",
        },
        p: {
          en: "Prices are set by the organizer in tenge. Any processing fee is shown before payment.",
          ru: "Цены устанавливает организатор в тенге. Сервисный сбор, если он есть, показывается до оплаты.",
          kk: "Бағаны ұйымдастырушы теңгемен белгілейді. Қызмет алымы болса, ол төлемге дейін көрсетіледі.",
        },
      },
      {
        h: { en: "4. Refunds", ru: "4. Возврат", kk: "4. Қайтару" },
        p: {
          en: "Refunds follow the organizer's refund policy on the event page. If an event is cancelled, paid tickets are refunded.",
          ru: "Возврат идёт по правилам организатора на странице события. Если событие отменено, оплаченные билеты возвращаются.",
          kk: "Қайтару іс-шара бетіндегі ұйымдастырушы ережесі бойынша жүреді. Іс-шара тоқтатылса, төленген билеттер қайтарылады.",
        },
      },
      {
        h: { en: "5. Entry", ru: "5. Вход", kk: "5. Кіру" },
        p: {
          en: "Each QR code lets one person in once. Do not share your ticket: the first scan wins.",
          ru: "Каждый QR-код пропускает одного человека один раз. Не передавайте билет: засчитывается первое сканирование.",
          kk: "Әр QR-код бір адамды бір рет кіргізеді. Билетті бөліспеңіз: алғашқы сканерлеу ғана есептеледі.",
        },
      },
    ],
  },
  "privacy-policy": {
    title: {
      en: "Privacy policy",
      ru: "Политика конфиденциальности",
      kk: "Құпиялылық саясаты",
    },
    draft: true,
    lede: {
      en: "What data BiletFlow keeps and why.",
      ru: "Какие данные хранит BiletFlow и зачем.",
      kk: "BiletFlow қандай деректерді не үшін сақтайды.",
    },
    sections: [
      {
        h: { en: "What we keep", ru: "Что мы храним", kk: "Не сақтаймыз" },
        p: {
          en: "Your name, email and phone if you add it, your orders and tickets, and support conversations.",
          ru: "Имя, email и телефон, если вы его укажете, ваши заказы и билеты, а также переписку с поддержкой.",
          kk: "Атыңыз, email және көрсетсеңіз телефоныңыз, тапсырыстарыңыз бен билеттеріңіз, қолдаумен хат алмасу.",
        },
      },
      {
        h: { en: "Who sees it", ru: "Кто это видит", kk: "Оны кім көреді" },
        p: {
          en: "The organizer of an event sees the attendee names and emails for that event so they can check you in. Platform staff see data only to handle support and moderation.",
          ru: "Организатор события видит имена и email участников этого события, чтобы пропустить их на вход. Сотрудники платформы видят данные только для поддержки и модерации.",
          kk: "Іс-шара ұйымдастырушысы кіргізу үшін сол іс-шара қатысушыларының аты мен email-ін көреді. Платформа қызметкерлері деректерді тек қолдау және модерация үшін көреді.",
        },
      },
      {
        h: { en: "Your choices", ru: "Ваши права", kk: "Сіздің құқықтарыңыз" },
        p: {
          en: "You can change your name, phone and language in account settings. To delete your account, open a support case.",
          ru: "Имя, телефон и язык можно изменить в настройках кабинета. Чтобы удалить аккаунт, создайте обращение в поддержку.",
          kk: "Атыңызды, телефоныңызды және тілді кабинет баптауларында өзгертуге болады. Аккаунтты жою үшін қолдауға өтініш жіберіңіз.",
        },
      },
    ],
  },
};

export const organizerLanding = {
  title: {
    en: "Sell tickets with BiletFlow",
    ru: "Продавайте билеты с BiletFlow",
    kk: "BiletFlow арқылы билет сатыңыз",
  },
  lede: {
    en: "Create an event in minutes, sell paid tickets or run free registration, and see every sale in one place.",
    ru: "Создайте событие за несколько минут, продавайте платные билеты или собирайте бесплатную регистрацию и видите все продажи в одном месте.",
    kk: "Іс-шараны бірнеше минутта жасаңыз, ақылы билет сатыңыз немесе тегін тіркеу жүргізіңіз және барлық сатылымды бір жерден көріңіз.",
  },
  cta: {
    en: "Become an organizer",
    ru: "Стать организатором",
    kk: "Ұйымдастырушы болу",
  },
  benefits: [
    {
      h: { en: "Self-service", ru: "Всё сами", kk: "Өзіңіз басқарасыз" },
      p: {
        en: "No calls or contracts to start: profile, event and tickets are set up in the workspace.",
        ru: "Чтобы начать, не нужны звонки и договоры: профиль, событие и билеты настраиваются в кабинете.",
        kk: "Бастау үшін қоңырау мен шарт керек емес: профиль, іс-шара және билеттер кабинетте бапталады.",
      },
    },
    {
      h: { en: "Promo with QR", ru: "Промо с QR", kk: "QR арқылы промо" },
      p: {
        en: "Campaign links and QR codes apply a promo code automatically and show which channel sold the tickets.",
        ru: "Ссылки и QR-коды кампаний сами подставляют промокод и показывают, какой канал продал билеты.",
        kk: "Науқан сілтемелері мен QR-кодтар промокодты өзі қолданып, билетті қай арна сатқанын көрсетеді.",
      },
    },
    {
      h: {
        en: "Seats and check-in",
        ru: "Места и вход",
        kk: "Орындар мен кіру",
      },
      p: {
        en: "Reserved seating with a hall map, staff accounts and a mobile scanner for the door.",
        ru: "Продажа мест по схеме зала, аккаунты для сотрудников и мобильный сканер на входе.",
        kk: "Зал схемасы бойынша орын сату, қызметкер аккаунттары және кіреберіске мобильді сканер.",
      },
    },
  ],
  steps: [
    {
      en: "Create an organizer profile",
      ru: "Создайте профиль организатора",
      kk: "Ұйымдастырушы профилін ашыңыз",
    },
    {
      en: "Add the event, tickets and seating",
      ru: "Добавьте событие, билеты и схему зала",
      kk: "Іс-шара, билет және зал схемасын қосыңыз",
    },
    {
      en: "Publish: free events go live right away, paid sales start after activation",
      ru: "Опубликуйте: бесплатные события доступны сразу, платные продажи — после активации",
      kk: "Жариялаңыз: тегін іс-шаралар бірден, ақылы сатылым белсендіруден кейін басталады",
    },
    {
      en: "Follow sales, attendees and campaigns in analytics",
      ru: "Следите за продажами, участниками и кампаниями в аналитике",
      kk: "Сатылымды, қатысушыларды және науқандарды аналитикада бақылаңыз",
    },
  ],
};
