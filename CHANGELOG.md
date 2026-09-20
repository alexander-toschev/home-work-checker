# Change list / Changelog

## 1.0.1 — 2026-09-20

- RU: предупреждения stderr после JSON больше не скрывают корректный результат последней проверочной ячейки; исходный код студента не изменяется.
- EN: stderr warnings following the grading JSON no longer hide a valid result from the final grading cell; student source is unchanged.
- Проверка / Validation: regression test for a trailing NumPy-style warning, plus existing checker and similarity tests.


## 1.0.0 — 2026-09-20

Первая явно нумерованная версия. Предыдущая версия не имела VERSION или тега релиза.
First explicitly versioned release; the previous state had no VERSION file or release tag.

### Изменено / Changed

- Checker проверяет локальный пакет и передаёт данные ассистенту. Операции Google выполняет ассистент отдельно.
  Local checks and assistant handoff replace direct Google operations.
- Оригиналы сохраняются и проверяются до исполнения кода. Время запуска включает микросекунды.
  Originals are verified before execution; run IDs include microseconds.
- Штраф рассчитывается по утверждённой политике и доверенному времени сдачи. Извлечённый балл остаётся без повторного штрафа.
  Approved policy and trusted receipt time determine penalties; extracted scores are preserved.
- Исторические CSV содержат попытки, а не заменяют таблицу лучших оценок.
  Historical CSVs retain attempts, rather than replacing the best-score sheet.

### Добавлено / Added

- `assistant_handoff.json`: версия checker, исходные данные, SHA-256, квитанция сдачи, расчёт штрафа и причины ручной проверки.
  Versioned handoff with claims, SHA-256, receipt, penalty calculation and review holds.
- Сравнение добавленных комментариев, пояснений и docstring с текущими и архивными работами того же ДЗ. Общий текст исходного шаблона исключается.
  Same-assignment review compares added prose across current and archived submissions, excluding template text.
- Проверка оставленного имени и конфликтов с доверенными данными. Кириллица/латиница дают кандидатов, а не автоматическое объединение студентов.
  Retained names and identity conflicts are flagged; transliteration suggests candidates without automatic merges.
- `similarity_review.json` и `.md`: фрагменты, позиции, пары файлов для решения преподавателя. Короткий одинаковый код сам по себе не вызывает сигнал.
  Evidence reports support teacher decisions; short-code similarity alone does not trigger a case.
- Проверки штрафа: граница срока, часовой пояс, предел, шкала, отсутствие политики и запрет повторного штрафа.
  Penalty checks cover boundary, timezone, cap, scale, missing policy and double penalties.
- `VERSION` и версия checker в отчёте, отдельно от версии схемы данных.
  VERSION and checker version in the handoff, separate from the schema version.

### Удалено / Removed

- Авторизация Google, установка Google-клиентов, встроенный экспорт и очистка листа.
  Google authentication, Google-client installation, built-in export and sheet clearing.

### Миграция / Migration

Нужен полный комплект: `home-work-checker.ipynb`, `submission_review.py`, `checker_handoff.py`, `VERSION`. Перед приёмом оценок задайте доверенные данные сдачи, оригинальные шаблоны и утверждённые политики. Неизвестные данные требуют ручной проверки. Ассистент читает текущую Google-таблицу и сохраняет только лучший одобренный результат. Все попытки остаются в архиве.

Use the notebook, both Python modules and VERSION together. Configure trusted receipts, original templates and approved policies. Missing information requires review. The assistant reads the current sheet and preserves the best approved result, keeping every attempt archived.

### Проверено / Validation

15 тестов на синтетических данных: сбои, неверные баллы, архив до исполнения, штрафы, квитанции, исключение шаблона, имена, транслитерация, повторные попытки, архивное сравнение и короткий код. Реальные студенческие работы не запускались, Google-таблицы не изменялись.

15 synthetic-data tests cover failures, scores, pre-execution archival, penalties, receipts, boilerplate, names, transliteration, resubmissions, history and short code. Tests execute no real student submissions and modify no Google Sheets.
