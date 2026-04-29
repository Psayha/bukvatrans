import { Link } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const FEATURES = [
  {
    icon: '🎙️',
    title: 'Любой источник',
    desc: 'Файл с компьютера, YouTube, Rutube, VK Видео или прямая ссылка на MP3/MP4.',
  },
  {
    icon: '⚡',
    title: 'Быстро и точно',
    desc: 'Groq Whisper обрабатывает час аудио меньше чем за минуту с высокой точностью.',
  },
  {
    icon: '🤖',
    title: 'AI-конспект',
    desc: 'Автоматическое резюме с ключевыми тезисами — экономит время на изучение материала.',
  },
  {
    icon: '📱',
    title: 'Telegram-бот',
    desc: 'Отправьте голосовое или ссылку прямо в бот — результат придёт в чат.',
  },
]

const STEPS = [
  { n: '1', text: 'Загрузите файл или вставьте ссылку на видео' },
  { n: '2', text: 'Мы транскрибируем аудио в текст с помощью AI' },
  { n: '3', text: 'Получите текст и AI-конспект, скопируйте или скачайте' },
]

const PLANS = [
  { label: 'Безлимит 7 дней', price: '249 ₽', period: '7 дней', highlight: false },
  { label: 'Безлимит 30 дней', price: '549 ₽', period: '30 дней', highlight: true },
  { label: 'Безлимит 6 месяцев', price: '2 499 ₽', period: '6 месяцев', highlight: false },
]

export default function Landing() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <span className="text-blue-600 font-bold text-lg">Littera</span>
          <div className="flex gap-3">
            {isAuthenticated ? (
              <Link
                to="/app"
                className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                Открыть приложение
              </Link>
            ) : (
              <>
                <Link to="/login" className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">
                  Войти
                </Link>
                <Link
                  to="/register"
                  className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
                >
                  Попробовать бесплатно
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 py-20 text-center">
        <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-5">
          Транскрибируйте аудио
          <br />
          <span className="text-blue-600">и видео за секунды</span>
        </h1>
        <p className="text-lg text-gray-500 max-w-xl mx-auto mb-8">
          YouTube, Rutube, VK, файлы с компьютера — загрузите и получите точный текст с
          AI-конспектом. Первые 3 транскрипции бесплатно.
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            to="/register"
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Попробовать бесплатно
          </Link>
          <Link
            to="/login"
            className="px-6 py-2.5 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            Войти
          </Link>
        </div>
        <p className="text-xs text-gray-400 mt-4">Без карты · 3 транскрипции бесплатно</p>
      </section>

      {/* How it works */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-2xl font-bold text-center mb-10">Как это работает</h2>
          <div className="flex flex-col sm:flex-row gap-6 justify-center">
            {STEPS.map((s) => (
              <div key={s.n} className="flex-1 text-center max-w-xs mx-auto">
                <div className="w-10 h-10 rounded-full bg-blue-600 text-white text-lg font-bold flex items-center justify-center mx-auto mb-3">
                  {s.n}
                </div>
                <p className="text-sm text-gray-700">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-bold text-center mb-10">Возможности</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="border rounded-lg p-5">
              <div className="text-2xl mb-2">{f.icon}</div>
              <h3 className="font-semibold mb-1">{f.title}</h3>
              <p className="text-sm text-gray-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-2xl font-bold text-center mb-3">Тарифы</h2>
          <p className="text-center text-gray-500 text-sm mb-10">
            Начните бесплатно — 3 транскрипции без регистрации карты
          </p>
          <div className="grid sm:grid-cols-3 gap-5 max-w-3xl mx-auto">
            {PLANS.map((p) => (
              <div
                key={p.label}
                className={`rounded-xl p-6 border ${
                  p.highlight ? 'border-blue-500 bg-blue-50 shadow-md' : 'bg-white'
                }`}
              >
                {p.highlight && (
                  <div className="text-xs font-semibold text-blue-600 mb-2 uppercase tracking-wide">
                    Популярный
                  </div>
                )}
                <div className="text-2xl font-bold mb-1">{p.price}</div>
                <div className="text-sm text-gray-500 mb-4">{p.period}</div>
                <div className="text-sm font-medium">Безлимитная транскрибация</div>
                <div className="text-sm text-gray-500 mt-1">AI-конспект включён</div>
                <Link
                  to="/register"
                  className={`mt-5 block text-center py-2 rounded-lg text-sm font-medium ${
                    p.highlight
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'border hover:bg-gray-50'
                  }`}
                >
                  Выбрать
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 text-center text-xs text-gray-400">
        <div className="flex justify-center gap-4 mb-2">
          <a href="/privacy" className="hover:text-gray-600">Политика конфиденциальности</a>
          <a href="/terms" className="hover:text-gray-600">Пользовательское соглашение</a>
        </div>
        <p>© {new Date().getFullYear()} Littera</p>
      </footer>
    </div>
  )
}
