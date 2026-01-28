Структура IMPLEMENTATION_GUIDELINES_v0.md

Статус документа и границы

Общие инженерные принципы (соответствие spec, fail-closed, детерминизм)

Артефакты: схемы, валидация, сериализация

determinism_key: вычисление, хранение, использование

Кеширование и повторное использование результатов

Ошибки: taxonomy, propagation, observability

Трассировка: correlation ids, минимальный набор событий

Тестовый контур: unit/contract/golden/replay

Управление версиями: specs, policies, environment

Чек-листы (pre-commit, pre-release, incident)

IMPLEMENTATION_GUIDELINES_v0.md
1. Статус и границы

Document: IMPLEMENTATION_GUIDELINES_v0.md
Version: v0
Status: SUBORDINATE TO ARCHITECTURE (non-canonical)

Эти guidelines:

описывают как реализовывать зафиксированные контракты,

MUST NOT добавлять “умное поведение” ролям,

MUST быть совместимы с RUNTIME_POLICIES_v0.

2. Общие инженерные принципы

MUST

Реализовывать роли как чистые функции от входного артефакта к выходному артефакту (или отказу).

Валидация входа — до любой обработки.

Любая неоднозначность → отказ, если spec не разрешает.

SHOULD

Держать реализацию роли минимальной: только то, что требуется spec’ом.

Иметь “strict mode” по умолчанию (он же прод).

MUST NOT

Встраивать в роль восстановление/ремедиацию “по смыслу” (это уже новая логика).

3. Артефакты: схемы, валидация, сериализация

MUST

Для каждого *_v0 артефакта иметь формальную схему (JSON Schema / Pydantic / protobuf — выбор реализации вне документа).

Любая сериализация для сравнения/логов/кеша MUST быть канонической и стабильной.

SHOULD

Отделять:

“payload” артефакта (то, что регламентирует spec),

“runtime metadata” (trace ids, hashes) — хранить вне payload, если spec не разрешает иначе.

4. determinism_key: вычисление, хранение, использование

MUST

Реализовать одну функцию compute_determinism_key_v0(...), используемую везде.

Производить seed модели из determinism_key по фиксированному правилу (например, hash → uint32), если seed доступен.

Не допускать альтернативных вычислений ключа “в разных местах”.

SHOULD

Хранить рядом:

input_hash (канонический хэш входного артефакта),

spec_bundle_hash (набор версий spec’ов),

runtime_policy_hash.

5. Кеширование и повторное использование результатов

MUST

Кеш MUST быть ключевым: cache_key = determinism_key + role_id + artifact_type_version.

Cache-hit MUST возвращать результат байт-в-байт идентичный тому, что был сохранён.

SHOULD

Разделять кэш:

на уровне роли (role output cache),

на уровне всего run (assembled final output),
при этом не менять архитектурные границы.

MUST NOT

Делать “семантический” кэш по приблизительному совпадению текста.

6. Ошибки: taxonomy, propagation, observability

MUST

Использовать фиксированную taxonomy error_code для v0 (единый словарь рантайма).

Ошибка роли MUST подниматься наверх без трансформации смысла (можно оборачивать инфраструктурной диагностикой, но не менять класс ошибки).

SHOULD

Отличать:

invalid input (пользователь/входной уровень),

contract violation (межрольный),

runtime failure (инфраструктура).

7. Трассировка

MUST

Пробрасывать trace_id, run_id, determinism_key сквозь весь прогон.

Логировать события в фиксированном порядке.

SHOULD

Иметь единый формат события: {ts?, seq, role_id, event_type, in_hash, out_hash, error?}
(время ts может быть, но MUST NOT влиять на determinism_key и на логику).

8. Тестовый контур

MUST

Unit tests: чистые функции, стабильные фикстуры.

Contract tests: схема/тип/обязательные поля.

Golden tests: эталонные артефакты на фиксированном наборе входов.

Replay tests: восстановление run из сохранённых входов.

SHOULD

Property tests на сериализацию/каноникализацию (не меняет ли порядок, пробелы, переводы строк).

9. Управление версиями

MUST

Любое изменение:

spec’ов (не применимо здесь, они immutable),

runtime policies,

implementation guidelines,

окружения/модели,
должно быть выражено версиями и отражено в determinism_key.

SHOULD

Ввести “manifest” прогона (run manifest): список версий spec/policy/env + hashes входов/выходов.

10. Чек-листы
10.1. Pre-commit (MUST)

 Валидация входов до обработки

 Каноническая сериализация для hashing/compare

 Отсутствие нефиксированной случайности

 Determinism tests (N=3) зелёные

 Fail-closed tests зелёные

10.2. Pre-release (MUST)

 Golden suite зелёный

 Replay suite зелёный

 Обновлён runtime policy / guidelines version при изменениях исполнения

 Зафиксированы model/env versions

10.3. Incident / Debug (SHOULD)

 Снять run manifest

 Сравнить determinism_key и input_hash

 Проверить drift окружения (model/version/tokenizer)

 Проверить порядок событий/логов на недетерминизм