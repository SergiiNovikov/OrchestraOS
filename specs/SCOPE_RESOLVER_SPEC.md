Scope Resolver
Architecture Specification v0

Проект: «Разработка»
Статус: архитектурно завершён
Версия: v0 (baseline)
Тип роли: Stateless, boundary-enforcing
Upstream: Front Manager
Downstream: Intent Interpreter

1. Назначение роли

Scope Resolver — инфраструктурная роль, предназначенная для определения допустимого контура обработки пользовательского запроса на основе Request Envelope, без интерпретации намерений и без добавления нового смысла.

Роль служит фильтром и ограничителем, а не интерпретатором или планировщиком.

2. Позиция в системе

Вход: Request Envelope (immutable, read-only)

Выход: Scoped Request

Состояние: отсутствует (stateless)

Взаимодействие с пользователем: отсутствует

Доступ к диалогу: отсутствует

Доступ к контексту Front Manager: отсутствует

3. Предусловия запуска

Scope Resolver запускается только если:

maturity == MATURE

Во всех остальных случаях роль не активируется.

4. Входной контракт (read-only)

Разрешённые поля для чтения:

schema_version

mode

baseline_norm

language

intent (label класса запроса)

maturity

policy_flags

contradictions_detected

contradictions_summary

routing_hint

determinism_key

Жёсткие запреты

Scope Resolver не читает и не использует:

freeze_candidate (по смыслу или для вывода)

историю изменений

любые поля вне списка выше

Отсутствие данных ≠ разрешение на гипотезы.

5. Определение Scope

Scope — формальная рамка допустимой downstream-обработки запроса.

Scope не является:

целью пользователя;

интерпретацией намерения;

планом действий.

Scope является:

классификацией допустимого контура обработки;

набором разрешений и запретов;

сигналом для downstream-ролей о границах ответственности.

6. Scope Taxonomy v0
6.1. Классы контура (scope_class)
Код	Название	Описание
S0	META_SYSTEM	Запросы о системе, ролях, контрактах, инвариантах
S1	PRODUCT_ARCH_SPEC	Архитектурная спецификация без реализации
S2	IMPLEMENTATION_REQUEST	Реализация, код, технологии
S3	ANALYSIS_CRITIQUE	Анализ, критика, ревью
S4	OPERATIONAL_EXECUTION	Выполнение реальных действий
S5	AMBIGUOUS_OR_MULTI_SCOPE	Несколько конкурирующих контуров
S6	POLICY_SENSITIVE	Запросы с policy-флагами
7. Правила классификации
7.1. Детерминизм

При одинаковом наборе входных read-only полей результат обязан быть идентичным.

7.2. Приоритеты (строгий порядок)

Policy override
Если policy_flags не пуст → S6_POLICY_SENSITIVE
(с обязательным secondary_scope_class)

Meta/system маркеры → S0_META_SYSTEM

Архитектурная спецификация → S1_PRODUCT_ARCH_SPEC

Реализация / код → S2_IMPLEMENTATION_REQUEST

Критика / ревью → S3_ANALYSIS_CRITIQUE

Операционное выполнение → S4_OPERATIONAL_EXECUTION

Конфликт / неоднозначность → S5_AMBIGUOUS_OR_MULTI_SCOPE

7.3. Противоречия

contradictions_detected == true не меняет scope_class

Информация о противоречиях обязана быть перенесена в Scoped Request

7.4. Routing Hint

Не команда

Используется только как tie-breaker при S5

Никогда не ломает детерминизм

8. Scoped Request — выходной артефакт
8.1. Schema v0
scoped_request:
  schema_version: "scoped_request_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    determinism_key: string?

  input_fingerprint:
    baseline_norm_hash: string
    language: string?

  carryover_labels:
    intent: enum
    maturity: "MATURE"
    policy_flags: list[enum]?
    contradictions_detected: boolean
    contradictions_summary: list[text]?

  scope:
    scope_class: enum
    secondary_scope_class: enum?
    scope_confidence: number   # 0..1
    allowed_contours: list[enum]
    disallowed_contours: list[enum]
    required_by_contract: list[text]

  handoff:
    target_role: "intent_interpreter"
    handoff_payload:
      baseline_norm: text
    notes_for_downstream: list[text]

9. Инварианты Scoped Request

Никакого нового смысла

Никаких гипотез

baseline_norm передаётся без изменений

notes_for_downstream содержат только ограничения

Для S6_POLICY_SENSITIVE:

secondary_scope_class обязателен

10. Allowed / Disallowed Contours (пример v0)

Контуры (enum-уровень):

CONTOUR_META_ONLY

CONTOUR_ARCH_SPEC_ONLY

CONTOUR_IMPLEMENTATION_ALLOWED

CONTOUR_CRITIQUE_ALLOWED

CONTOUR_EXECUTION_DISALLOWED

CONTOUR_NEEDS_DOWNSTREAM_DISAMBIGUATION

CONTOUR_NEEDS_POLICY_CHECK

Примеры правил:

S1 → allowed: ARCH_SPEC_ONLY; disallowed: IMPLEMENTATION, EXECUTION

S5 → allowed: NEEDS_DOWNSTREAM_DISAMBIGUATION

S6 → allowed: NEEDS_POLICY_CHECK; disallowed: EXECUTION

11. Отказные сценарии

Scope Resolver не отказывает пользователю, но может:

вернуть S6_POLICY_SENSITIVE → downstream обязан пройти policy-гейт

вернуть S5_AMBIGUOUS_OR_MULTI_SCOPE → downstream не имеет права выбирать узкий контур без доп. этапа

12. Граница ответственности с Intent Interpreter

Scope Resolver:

классифицирует контур

задаёт рамки допустимости

переносит метки и сигналы

Intent Interpreter:

интерпретирует намерение

извлекает цель

принимает решения внутри разрешённого scope

13. Архитектурная фиксация

Роль архитектурно завершена

Scope Taxonomy v0 зафиксирована

Scoped Request Schema v0 зафиксирована

Пересечение ответственности с соседними ролями отсутствует