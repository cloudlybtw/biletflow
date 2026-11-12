// Editorial previews are deliberately separate from bookable inventory.
export const heroCopy = {
  en: { showcase: 'Upcoming experiences', emptyCategory: 'No upcoming events in this category. Try another category.', upcoming: 'Upcoming', sport: 'Sport', concerts: 'Concerts', friends: 'With friends', pause: 'Pause slideshow', play: 'Play slideshow', previous: 'Previous ticket', next: 'Next ticket', carousel: 'Featured experiences', preview: 'Preview · not valid for entry', date: 'Date to be announced', football: 'Almaty / Astana', footballBody: 'A demo football fixture. The roar, the lights, the beautiful game.', community: 'Good company. Great stories.', communityBody: 'Make something, meet someone. A community afternoon in Kazakhstan.', culture: 'An evening less ordinary.', cultureBody: 'New perspectives, live stages, and a reason to go out.', music: 'Feel every note.', musicBody: 'Find your place in the crowd. Discover the next live sound.', city: 'Across Kazakhstan', tear: 'Your next memory starts here.' },
  ru: { showcase: 'Ближайшие события', emptyCategory: 'В этой категории пока нет ближайших событий. Выберите другую.', upcoming: 'Скоро', sport: 'Спорт', concerts: 'Концерты', friends: 'С друзьями', pause: 'Приостановить слайды', play: 'Включить слайды', previous: 'Предыдущий билет', next: 'Следующий билет', carousel: 'Избранные события', preview: 'Превью · не для входа', date: 'Дата уточняется', football: 'Алматы / Астана', footballBody: 'Демонстрационный футбольный матч. Свет трибун и энергия игры.', community: 'Свои люди. Новые истории.', communityBody: 'Создавайте, знакомьтесь и проводите время вместе.', culture: 'Вечер вне привычного.', cultureBody: 'Новые взгляды, живые сцены и повод выйти из дома.', music: 'Почувствуйте каждую ноту.', musicBody: 'Найдите своё место в толпе. Откройте новый живой звук.', city: 'По всему Казахстану', tear: 'Здесь начинаются ваши воспоминания.' },
  kk: { showcase: 'Алдағы іс-шаралар', emptyCategory: 'Бұл санатта алдағы іс-шаралар жоқ. Басқа санатты таңдаңыз.', upcoming: 'Жақында', sport: 'Спорт', concerts: 'Концерттер', friends: 'Достармен', pause: 'Слайдтарды тоқтату', play: 'Слайдтарды қосу', previous: 'Алдыңғы билет', next: 'Келесі билет', carousel: 'Таңдаулы іс-шаралар', preview: 'Алдын ала көрініс · кіруге жарамсыз', date: 'Күні нақтылануда', football: 'Алматы / Астана', footballBody: 'Демонстрациялық футбол матчы. Трибуналар мен ойын қуаты.', community: 'Жақсы орта. Жаңа оқиғалар.', communityBody: 'Бірге жасаңыз, танысыңыз, уақыт өткізіңіз.', culture: 'Ерекше кешке қадам.', cultureBody: 'Жаңа көзқарас, жанды сахна және жаңа әсерлер.', music: 'Әр нотаны сезініңіз.', musicBody: 'Жанды әуен әлемінен өз орныңызды табыңыз.', city: 'Қазақстан бойынша', tear: 'Жаңа естеліктер осы жерден басталады.' },
};
export const heroThemes = [
  { key: 'upcoming', category: 'culture', image: 'theatre', headline: 'culture', description: 'cultureBody' },
  { key: 'sport', category: 'sport', image: 'sport', headline: 'football', description: 'footballBody' },
  { key: 'concerts', category: 'music', image: 'music', headline: 'music', description: 'musicBody' },
  { key: 'friends', category: 'workshop', image: 'campus', headline: 'community', description: 'communityBody' },
];

// Showcase filters are independent of discovery filters and preserve event identity.
export function showcaseEvents(events, category, now = new Date()) {
  const categories = { sport: ["sport"], concerts: ["music"], friends: ["workshop", "campus"] };
  return [...new Map(events
    .filter((event) => new Date(event.startsAt) >= now &&
      (category === "upcoming" || categories[category]?.includes(event.category)))
    .map((event) => [event.id, event])).values()]
    .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt));
}
