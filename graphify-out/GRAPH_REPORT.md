# Graph Report - System/adam/  (2026-05-15)

## Corpus Check
- 30 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 646 nodes · 1090 edges · 47 communities (36 shown, 11 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 145 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]

## God Nodes (most connected - your core abstractions)
1. `VoiceLoopController` - 42 edges
2. `EspAudioHealthMonitor` - 32 edges
3. `SceneWorker` - 30 edges
4. `SessionWatcher` - 30 edges
5. `EpisodicMemory` - 29 edges
6. `MCUClient` - 25 edges
7. `CameraReader` - 23 edges
8. `SessionAccumulator` - 23 edges
9. `TuningStore` - 17 edges
10. `EchoGate` - 15 edges

## Surprising Connections (you probably didn't know these)
- `VoiceLoopController` --uses--> `ActionLayer`  [INFERRED]
  System/Orchestrator.py → System/adam/action.py
- `SceneWorker` --uses--> `ActionLayer`  [INFERRED]
  System/Orchestrator.py → System/adam/action.py
- `SessionWatcher` --uses--> `ActionLayer`  [INFERRED]
  System/Orchestrator.py → System/adam/action.py
- `EspAudioHealthMonitor` --uses--> `ActionLayer`  [INFERRED]
  System/Orchestrator.py → System/adam/action.py
- `_rebuild_clients()` --calls--> `ActionLayer`  [INFERRED]
  System/Orchestrator.py → System/adam/action.py

## Communities (47 total, 11 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (32): _aplay_devices(), _arecord_devices(), _decode_to_pcm(), _filter_alsa_devices(), _load_calibration_profile(), Runtime API extensions for the Adam Chip orchestrator.  Exposes config read/writ, Save per-source OWW threshold to wake_calibration_profiles.json., Load per-source OWW threshold from wake_calibration_profiles.json. (+24 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (8): _decode_json(), DeviceResult, MCUClient, Restart port-81 stream server — clears stale camera/audio/speaker connections., Return ESP32 heap/uptime diagnostics., Soft-reset ESP32. Returns immediately — device reboots after ~300ms., OpenAIChatClient, ServiceHealth

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (14): WebRTC VAD wrapper — stateless, CPU-only, no PyTorch required.  Example::      v, Drop-in replacement for Silero VAD in VoiceLoopController.      aggressiveness —, Return 1.0 if speech detected, 0.0 if not.          audio_bytes: raw 16-bit mono, Convenience wrapper returning bool instead of float., No-op — WebRTC VAD is stateless. Exists for API compatibility., WebRtcVadWrapper, _capture_device_for(), listen_status() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (8): CameraReader, Stop and restart the camera capture thread., Persistent background camera capture with thread-safe frame buffer.      When pr, Fetch single JPEG from ESP32 GET /capture (port 80).          One-shot request —, One-shot Jetson camera frame for fallback mode., Thread-safe ring buffer of recent VLM scene descriptions., Apply video config changes at runtime. Returns True if restart is needed., SceneDescriptionBuffer

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (16): _debug_scene_updates(), _module_flags(), # NOTE: runtime_state["speaking"] и event "tts_started" больше НЕ ставятся здесь, _result_or_raise(), ui_audio(), ui_camera(), ui_camera_preset(), ui_pca_channel() (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (11): EpisodicMemory, _parse_ts(), Persistence-слой для эпизодической памяти + semantic markdown + gate-логи., Append одного эпизода в jsonl за день ts_end., Идёт по всем jsonl, отдаёт Episode по одному., Возвращает {id: last_ts} для быстрого cooldown lookup., Помечает эпизоды consolidated=True. Возвращает кол-во затронутых., Удаляет старые записи. Возвращает stats {dropped, kept, files_removed}. (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (19): _dependency_errors(), _get_model(), health(), _load_model_with_fallback(), WhisperX ASR microservice — CUDA-optimized speech recognition for Jetson Orin., Transcribe a numpy array (float32, 16kHz) directly — used for warmup and interna, # NOTE: whisperx uses avg_logprob (NOT no_speech_prob which is faster-whisper on, Decode WAV bytes to float32 numpy array at 16kHz without requiring ffmpeg. (+11 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (14): _clamp01(), Episode, from_dict(), _from_iso(), Highlight, Episodic memory primitives для Адама.  `Episode` — одна запись на диалоговую сес, Rule-based salience-формула из Memory_Schema.md.      Возвращает float в [0..1]., Триггер записи: salience >= threshold OR introduced_name OR pinned. (+6 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (13): _build_context_body(), is_leading_noise(), _is_other_noise(), _is_sensors_header(), _is_vision_header(), LeadingNoiseFilter, PromptBuilder, Strip leading system-info echo lines from a full reply.      Returns (cleaned_te (+5 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (8): create_engine(), OpenWakeWordEngine, PorcupineEngine, Local wake word detection — runs entirely on CPU, <5ms per 80ms frame., Build from config. engine="openwakeword" → OpenWakeWordEngine with built-in VAD., Uses adam.onnx directly with built-in Silero VAD.      Debounced: requires N con, Picovoice Porcupine detector — requires a .ppn file and API key., WakeWordEngine

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (9): _deep_merge(), get_store(), Singleton-обёртка над Tuning. Перечитывает файл при изменении mtime.      Исполь, Reload from disk if mtime changed. Returns new Tuning if listeners should fire,, Возвращает актуальный Tuning, перечитывая файл если он изменился., Применяет частичное обновление, валидирует, сохраняет на диск.          Patch —, Полная замена настроек (без deep merge). Для UI-формы Restore defaults / Import., callback(tuning: Tuning) вызывается при изменении настроек. (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.17
Nodes (10): BaseHTTPRequestHandler, _eager_load(), _extract_text(), _infer(), _parse_vision_message(), Extract (prompt_text, jpeg_bytes) from OpenAI vision message list., Run VILA inference. Serialized via _INFER_LOCK (MLC is single-threaded)., Robustly extract string from nano_llm generate() result. (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (18): _commit_session_locked(), dialogue_turn(), _execute_action(), _extract_visitor_name(), _format_recent_episodic(), Returns full name (first + last/patronymic) or None.      Single-word names are, Простая эвристика для mood-метки gate-фильтра.      Возвращает один из: 'neutral, Закрывает текущую сессию, пишет эпизод если salience прошёл фильтр.      Должна (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.19
Nodes (14): ConsolidatorTuning, DiagnosticsTuning, LLMTuning, MemoryTuning, PromptTuning, Runtime-настройки персоны Адама.  `Tuning.json` редактируется из WebUI и hot-rel, Корневая модель runtime-настроек персоны., RecentInjectionTuning (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (4): _question_signature(), Растёт по ходу сессии, финализируется в Episode., Нормализованная сигнатура для дедупликации вопросов в рамках сессии., SessionAccumulator

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (6): _decode(), Synthesize text and return raw WAV bytes without triggering playback., Play WAV bytes locally. Blocks until playback completes.          Uses Popen (no, Kill the active aplay process (barge-in). Safe to call from any thread., split_sentences(), TTSClient

### Community 16 - "Community 16"
Cohesion: 0.15
Nodes (14): gate_summary(), _audio_level_monitor(), _compact_mcu(), _exhibition_gate(), gate(), lifespan(), listen_start(), listen_stop() (+6 more)

### Community 17 - "Community 17"
Cohesion: 0.2
Nodes (10): _clean_body(), EchoEntry, InjectedEcho, parse_echoes_file(), _parse_text(), Gate для пулов Echoes / Chinese.  Парсит файлы пула (`About/Echoes.md`, `About/C, То, что gate возвращает оркестратору для инжекта в prompt., Парсит .md-файл с блоками ```yaml --- frontmatter --- ``` + текст после.      Во (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (5): create_llm_client(), EspAudioHealthMonitor, Polls ESP32 /api/audio periodically and auto-switches mic profile when a channel, Recreate service clients after a Config.json patch.      Called from the /api/co, _rebuild_clients()

### Community 19 - "Community 19"
Cohesion: 0.24
Nodes (7): data_dir(), _deep_merge(), load(), mode(), persona_paths(), _resolve_path(), Settings

### Community 20 - "Community 20"
Cohesion: 0.27
Nodes (10): _dependency_errors(), _ensure_loaded(), health(), _load_model(), _play_wav(), _playback_commands(), speak(), synthesize() (+2 more)

### Community 21 - "Community 21"
Cohesion: 0.23
Nodes (6): EchoGate, Singleton-инстанс, который дёргается из оркестратора каждый turn., Перечитать файл если изменился. Возвращает число загруженных entries., Главная точка вызова. None или InjectedEcho.          Side-effect: при инжекте —, Просто увеличить счётчик turn'ов без попытки инжекта.          Используется когд, Tag-based матч: считаем сколько тегов entry присутствуют в transcript.

### Community 22 - "Community 22"
Cohesion: 0.23
Nodes (5): create_asr_client(), HTTP client for a Whisper-compatible ASR microservice (POST /transcribe → {"tran, HTTP client for ASR_WhisperX.py microservice (whisperx + CUDA).      API contrac, WhisperASRClient, WhisperXASRClient

### Community 23 - "Community 23"
Cohesion: 0.23
Nodes (9): events(), journal(), metrics(), adam-logviewer: read-only HTTP service for logs.  Runs independently from adam-o, Try fetching from orchestrator; return parsed JSON or None on any error., _run(), services(), tail_jsonl() (+1 more)

### Community 24 - "Community 24"
Cohesion: 0.2
Nodes (12): cue(), _orchestrated_startup(), _play_error_sound(), _play_success_sound(), Poll expected AI services until all healthy or 120 s deadline. Returns True if a, Sequential boot: wait for services → sound → warmup greeting → voice loop., Prime llama.cpp KV cache with the exact system prefix real voice turns use., _schedule_success_sound() (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.36
Nodes (3): Action, ActionLayer, _mood()

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (3): _extract_chat_text(), _is_chinese_dominant(), VLMClient

### Community 27 - "Community 27"
Cohesion: 0.31
Nodes (6): _alsa_device_available(), _extract_v4l2_device(), MediaHealth, MediaStatus, _probe_http_url(), _run()

### Community 28 - "Community 28"
Cohesion: 0.29
Nodes (8): all_services_status(), CommandStatus, docker_health(), Return {active, enabled, detail} for a systemd unit., Start or stop a systemd unit via sudo -n (requires NOPASSWD sudoers)., service_action(), service_status(), _systemctl()

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (9): agent_page(), dash_page(), debug_page(), _json_script_value(), _load(), legacy_agent(), legacy_dash(), legacy_debug() (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.38
Nodes (3): PowerGate, PowerStatus, _run()

### Community 33 - "Community 33"
Cohesion: 0.33
Nodes (3): Health adapter for the external NVIDIA Riva streaming ASR service.      Streamin, RivaASRConfig, RivaASRService

### Community 34 - "Community 34"
Cohesion: 0.6
Nodes (3): _local_playback_command(), play_local_sound(), SoundResult

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (3): System/adam — карта Python-модулей оркестратора, Модули (23), Правила доступа (обязательно)

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (4): _apply_wav_speed(), _prewarm_filler(), Rewrite WAV header to play `speed`x faster. Pitch shifts up proportionally     (, Pre-synthesize the configured filler phrase at the current playback speed     so

### Community 37 - "Community 37"
Cohesion: 0.67
Nodes (3): get_prompt_trace(), Список последних prompt-trace записей.      full=false — только метаданные (tran, _summarize_trace()

## Knowledge Gaps
- **117 isolated node(s):** `Core runtime modules for the Adam Chip exhibition agent.`, `Runtime API extensions for the Adam Chip orchestrator.  Exposes config read/writ`, `Save per-source OWW threshold to wake_calibration_profiles.json.`, `Load per-source OWW threshold from wake_calibration_profiles.json.`, `Persistent background camera capture with thread-safe frame buffer.      When pr` (+112 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `VoiceLoopController` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 8`, `Community 10`, `Community 13`, `Community 14`, `Community 15`, `Community 18`, `Community 19`, `Community 21`, `Community 22`, `Community 25`, `Community 26`, `Community 27`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Why does `EspAudioHealthMonitor` connect `Community 18` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 8`, `Community 10`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 19`, `Community 21`, `Community 22`, `Community 25`, `Community 26`, `Community 27`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `SceneWorker` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 8`, `Community 10`, `Community 13`, `Community 14`, `Community 15`, `Community 18`, `Community 19`, `Community 21`, `Community 22`, `Community 25`, `Community 26`, `Community 27`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `VoiceLoopController` (e.g. with `ActionLayer` and `RuntimeDeps`) actually correct?**
  _`VoiceLoopController` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `EspAudioHealthMonitor` (e.g. with `ActionLayer` and `RuntimeDeps`) actually correct?**
  _`EspAudioHealthMonitor` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `SceneWorker` (e.g. with `ActionLayer` and `RuntimeDeps`) actually correct?**
  _`SceneWorker` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `SessionWatcher` (e.g. with `ActionLayer` and `RuntimeDeps`) actually correct?**
  _`SessionWatcher` has 23 INFERRED edges - model-reasoned connections that need verification._