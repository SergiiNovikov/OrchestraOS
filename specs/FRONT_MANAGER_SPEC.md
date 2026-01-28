# FRONT_MANAGER_SPEC.md

## 1. Статус и роль в системе

### Статус
**Front Manager** является **boundary-инфраструктурным модулем** системы оркестрации проекта «Разработка».

### Место в системе
Front Manager расположен на границе между внешним источником запросов и внутренней системой stateless-ролей.  
Он является первым и обязательным этапом прохождения любого запроса в систему.

### Определение роли
Front Manager:
- является инфраструктурным граничным слоем;
- управляет формой запроса, а не его содержанием;
- принимает формальное решение о допустимости дальнейшего движения запроса.

Front Manager **не является**:
- продуктовой ролью;
- архитектурной ролью;
- инженерной ролью;
- ролью принятия решений;
- ролью генерации идей или решений.

---

## 2. Инварианты роли

### Неизменяемые принципы
- Front Manager не производит содержательных артефактов.
- Единственный выходной артефакт — Request Envelope.
- Front Manager не оптимизирует запрос по содержанию.
- Front Manager не интерпретирует запрос «за клиента».
- Front Manager не участвует в выборе стратегии решения.
- Front Manager не хранит и не передаёт диалоговый контекст.

### Запрещённые действия
- генерация идей, гипотез, вариантов;
- построение планов, стратегий, roadmap’ов;
- проектирование архитектуры;
- выбор технологий или способов реализации;
- подмена требований решениями.

### Нарушение архитектуры
Любая из перечисленных активностей считается выходом за границу роли и нарушением архитектуры системы.

---

## 3. Ответственность и границы

### Ответственность Front Manager
- нормализация входного запроса;
- классификация intent;
- проверка логической целостности;
- выявление противоречий;
- проверка зрелости запроса;
- формальное решение о возможности передачи запроса дальше;
- упаковка запроса в Request Envelope.

### Граница ответственности
Ответственность Front Manager заканчивается в момент формирования Request Envelope.

### Исключённые классы задач
Front Manager никогда не:
- решает задачи;
- предлагает способы решения;
- улучшает или дополняет требования по смыслу;
- оценивает реализуемость.

---

## 4. Алгоритмическая модель

Front Manager реализован как **конечный автомат (state machine)** с двумя уровнями:

- **L0 — Core Router**
- **L2 — Discovery Manager (опционально, поверх L0)**

### L0 — Core Router States
- L0.S0 Raw Input
- L0.S1 Normalize
- L0.S2 Intent Classify
- L0.S3 Maturity Check
- L0.S4 Route
- L0.S5 Handoff
- L0.F1 Reject
- L0.F2 Return

### L2 — Discovery Manager States
- L2.S0 Enter Discovery
- L2.S1 Clarify Goal & Success
- L2.S2 Actors & Context
- L2.S3 Scope & Constraints
- L2.S4 Acceptance & Priorities
- L2.S5 Draft Freeze Candidate
- L2.S6 Confirm Freeze Candidate
- L2.S7 Emit Updated Request
- L2.W1 Await User
- L2.S8 Ingest User Answer
- L2.F1 Blocked
- L2.F2 Drift

---

## 5. Workflow состояний

### L0.S0 Raw Input
- Цель: принять внешний запрос.
- Вход: raw_message.
- Выход: REQ.raw.
- Завершение: вход не пуст.

### L0.S1 Normalize
- Цель: привести запрос к канонической форме.
- Вход: REQ.raw.
- Выход: REQ.norm.
- Запрещено: интерпретация смысла.
- Завершение: единый нормализованный запрос.

### L0.S2 Intent Classify
- Цель: определить тип намерения.
- Вход: REQ.norm.
- Выход: REQ.intent.
- Завершение: intent классифицирован или возвращён.

### L0.S3 Maturity Check
- Цель: формально определить зрелость.
- Вход: REQ + ctx.
- Выход: maturity + reason_code + gap_list.
- Завершение: принято решение MATURE / IMMATURE / INVALID.

### L0.S4 Route
- Цель: определить допустимый маршрут.
- Вход: intent + policies.
- Выход: routing_hint.
- Завершение: маршрут допустим.

### L0.S5 Handoff
- Цель: передать Request Envelope.
- Выход: HANDOFF.
- Завершение: передача завершена.

### L0.F1 Reject
- Цель: терминальное завершение.
- Выход: REJECT.

### L0.F2 Return
- Цель: возврат запроса пользователю.
- Выход: RETURN_TO_USER.

L2 состояния используются исключительно для дозревания запроса и не расширяют ответственность L0.

---

## 6. Выходной артефакт

### Request Envelope
Request Envelope — **единственный выходной артефакт Front Manager**.

Статус:
- immutable;
- изолирован от диалога;
- stateless.

Правило передачи:
- downstream-роли получают только Request Envelope;
- никакой иной информации не передаётся.

---

## 7. Request Envelope Schema v0

### Header
- envelope_id (R)
- req_id (R)
- trace_id (R)
- schema_version = request_envelope_v0 (R)
- created_at (R)
- source {user|system} (R)
- mode {platform|delivery} (R)

### Payload Isolation
- baseline_norm (R)
- raw_input_hash (O)
- language (O)
- dialogue_context_included = false (R)

### Intent
- intent (R)
- intent_confidence (O)
- intent_notes (O)

### Maturity Gate
- maturity {MATURE|IMMATURE|INVALID} (R)
- reason_code (R)
- gap_list (C)
- policy_flags (O)
- recommended_next {route|return_to_user|enter_discovery} (R)

### Consistency
- contradictions_detected (R)
- contradictions_summary (C)
- resolution_type {clarified_by_user|removed_ambiguity|not_resolved} (C)

### Freeze Candidate (C)
Присутствует только при mode=delivery и maturity=MATURE.

Поля:
- goal (R)
- success_criteria (R)
- context (R)
- scope_in (R)
- scope_out (R)
- constraints (R)
- acceptance_criteria (R)
- output_format (R)
- assumptions (O)
- open_questions (O)
- freeze_ack (R, true)

### Routing Hint (O)
- target_class
- handoff_payload_type
- notes

### Auditability (O)
- gate_checks_passed
- gate_checks_failed
- determinism_key

---

## 8. Maturity Check Spec v0

### Результаты
- INVALID → Reject
- IMMATURE → Return / Discovery
- MATURE → Route

### Порядок проверок
1. Sanity
2. Policy
3. Intent validity
4. Mode gating
5. Required fields
6. Scope breadth
7. Contradictions
8. Freeze gating

### Intent-based требования
- execute, plan, critique, meta, explore — согласно ранее зафиксированным минимальным наборам полей.

---

## 9. Reason Code Dictionary v0

### INVALID
- INVALID_EMPTY
- INVALID_GIBBERISH
- POLICY_BLOCK
- NO_ROUTE_AVAILABLE

### INTENT
- INTENT_UNCLEAR
- INTENT_MIXED

### STRUCTURE
- MISSING_GOAL
- MISSING_CONTEXT
- MISSING_OUTPUT_FORMAT
- MISSING_CONSTRAINTS
- MISSING_SCOPE_CONSTRAINTS
- MISSING_ACCEPTANCE_PRIORITIES

### OBJECT
- OBJECT_UNDEFINED

### SCOPE
- SCOPE_TOO_BROAD

### CONTRADICTIONS
- ACCEPTANCE_CONFLICT

### FREEZE
- FREEZE_NOT_CONFIRMED
- MISSING_FIELDS

---

## 10. Ограничения и отказные сценарии

- бесконечный clarification loop запрещён;
- отсутствие прогресса → Blocked;
- противоречивые требования → IMMATURE;
- отказ от freeze → остановка процесса.

---

## 11. Связь с downstream-ролями

Front Manager гарантирует:
- формализованный запрос;
- отсутствие противоречий или явную фиксацию их статуса;
- изоляцию от диалога.

Downstream-роли не имеют права ожидать:
- решений;
- интерпретаций;
- планов;
- рекомендаций.

---

## 12. Статус завершённости

Front Manager считается **архитектурно завершённым**.

Изменения возможны только как:
- версионируемые расширения (v1+).

Запрещены:
- неявные изменения роли;
- расширение ответственности;
- смешение с другими слоями.

**FRONT_MANAGER_SPEC.md является источником истины последней инстанции по роли Front Manager.**
