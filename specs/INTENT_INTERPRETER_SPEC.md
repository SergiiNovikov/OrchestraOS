# INTENT_INTERPRETER_SPEC.md

## Статус и роль в системе

**Роль:** Intent Interpreter  
**Тип:** Stateless  
**Статус:** Канонический, v0, CLOSED  
**Upstream:** Scope Resolver  
**Downstream:** Task Decomposer  

Назначение роли — нормативная интерпретация намерения пользователя строго внутри разрешённого scope, с подготовкой детерминированного представления намерения для последующей декомпозиции.

---

## Инварианты роли

- Роль не хранит состояние.
- Входной артефакт является **read-only**.
- `baseline_norm` передаётся без изменений и не переписывается.
- `scope.allowed_contours` является жёстким ограничением.
- `scope.disallowed_contours` не могут быть нарушены.
- `required_by_contract` обязателен к учёту.
- Отсутствие данных не трактуется как разрешение на гипотезы.
- Выход должен быть детерминирован при одинаковом входе.

---

## Границы ответственности

**Intent Interpreter обязан:**
- Извлечь явное намерение пользователя.
- Зафиксировать системную цель запроса.
- Устранить смысловую двусмысленность в рамках разрешённого scope.
- Подготовить намерение к детерминированной декомпозиции.

**Intent Interpreter не имеет права:**
- Изменять или переопределять scope.
- Выходить за пределы `allowed_contours`.
- Планировать шаги или выполнять задачи.
- Декомпозировать задачи.
- Оптимизировать, улучшать или расширять намерение.
- Добавлять гипотезы или скрытые предположения.
- Модифицировать входной артефакт.

---

## Входной контракт (Scoped Request, read-only)

**Scoped Request Schema v0**

```yaml
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
    scope_confidence: number
    allowed_contours: list[enum]
    disallowed_contours: list[enum]
    required_by_contract: list[text]

  handoff:
    target_role: "intent_interpreter"
    handoff_payload:
      baseline_norm: text
    notes_for_downstream: list[text]
Определение Intent (нормативное)
Intent — это однозначно интерпретированная, формализованная системная цель пользовательского запроса, выведенная исключительно из baseline_norm, согласованная с allowed_contours, не нарушающая disallowed_contours и учитывающая required_by_contract, без добавления предположений.

Алгоритм извлечения намерения
Принять baseline_norm как единственный семантический источник.

Определить явную цель запроса, выраженную пользователем.

Сопоставить цель с разрешёнными контурами (allowed_contours).

Проверить отсутствие пересечений с disallowed_contours.

Учесть все элементы required_by_contract.

Зафиксировать намерение в канонической, недвусмысленной форме.

Обеспечить детерминированность результата.

Обработка двусмысленностей и конфликтов
Двусмысленность устраняется только за счёт:

явного содержания baseline_norm;

ограничений allowed_contours;

обязательств required_by_contract.

Если устранение двусмысленности невозможно без гипотез:

фиксируется состояние AMBIGUOUS_INTENT.

При наличии входных противоречий (contradictions_detected = true):

противоречия не разрешаются;

они отражаются в выходном артефакте как блокирующие.

Выходной артефакт (Schema v0)
Intent Package Schema v0

yaml
Копировать код
intent_package:
  schema_version: "intent_package_v0"

  identity:
    envelope_id: string
    req_id: string
    trace_id: string
    determinism_key: string?

  source_fingerprint:
    baseline_norm_hash: string

  intent_definition:
    intent_status: enum  # RESOLVED | AMBIGUOUS | BLOCKED
    intent_label: enum?
    intent_goal: text?
    constraints:
      allowed_contours: list[enum]
      required_by_contract: list[text]

  ambiguity_report:
    ambiguous: boolean
    ambiguity_reason: list[text]?

  conflict_report:
    conflicts_present: boolean
    conflict_summary: list[text]?

  handoff:
    target_role: "task_decomposer"
    notes_for_downstream: list[text]
Негативные и отказные сценарии
AMBIGUOUS_INTENT: намерение не может быть однозначно зафиксировано без гипотез.

BLOCKED: намерение противоречит disallowed_contours или обязательным контрактным требованиям.

В отказных сценариях Intent Interpreter:

не модифицирует вход;

не предлагает альтернатив;

возвращает формальный статус.

Граница с Task Decomposer
Единственный допустимый вход для Task Decomposer — intent_package_v0.

Task Decomposer не получает:

исходный baseline_norm;

полномочия на переинтерпретацию намерения;

разрешения на изменение intent-границ.

Intent Interpreter не влияет на логику декомпозиции.

Статус архитектурной завершённости
Документ INTENT_INTERPRETER_SPEC.md зафиксирован как канонический.
Изменения не допускаются без пересмотра upstream-контрактов.