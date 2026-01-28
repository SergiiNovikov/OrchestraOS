Appendix B
RUN_MANIFEST_SCHEMA_v0.md
1. Статус документа

Document: RUN_MANIFEST_SCHEMA_v0.md
Version: v0
Status: SUBORDINATE TO ARCHITECTURE (non-canonical)
Scope: машиночитаемый “паспорт прогона” (run), обеспечивающий воспроизводимость и аудит.

2. Назначение Run Manifest

Run Manifest фиксирует:

что было выполнено;

в каком окружении;

по каким входам;

с каким результатом.

Manifest не участвует в архитектурном pipeline и не передаётся между ролями.

3. Run Manifest Schema v0
run_manifest:
  schema_version: "run_manifest_v0"

  run_identity:
    run_id: string
    trace_id: string
    determinism_key: string

  inputs:
    primary_input_hash: string
    artifacts:
      - artifact_type: string
        artifact_version: string
        artifact_hash: string

  specs:
    - spec_name: string
      spec_version: string
      spec_hash: string

  runtime_policies:
    policy_version: string
    policy_hash: string

  implementation_guidelines:
    guidelines_version: string
    guidelines_hash: string

  environment:
    runtime_version: string
    model_id: string
    model_version: string
    tokenizer_version: string?

  execution_trace:
    - seq: integer
      role_id: string
      event_type: enum  # START | END | ERROR
      input_hash: string?
      output_hash: string?
      error_code: string?

  final_outcome:
    status: enum  # success | failure
    final_artifact_hash: string?

4. Инварианты Run Manifest

Run Manifest MUST быть детерминированно сериализуем.

Любое изменение, влияющее на результат, MUST отражаться в manifest.

Manifest MUST позволять воспроизвести run при наличии входных артефактов.

Manifest MUST NOT содержать пользовательский контент в открытом виде (только хэши).

5. Использование

Run Manifest используется для:

replay execution;

audit и post-mortem;

сравнения прогонов;

детекции drift’а окружения.

Run Manifest MUST NOT:

влиять на логику ролей;

использоваться как входной артефакт pipeline.

6. Статус завершённости

RUN_MANIFEST_SCHEMA_v0.md является зафиксированным нормативным приложением v0.

Изменения допускаются только через выпуск v1+.