# Adam-Chip

github.com/7teenzzz/Adam-Chip

Проект носит художественно-исследовательский характер и посвящен разработке локального AI-агента в edge-среде.

Adam Chip — это агентная система, исследующая границы субъектности, восприятия и действия в техносреде. Агент функционирует как когнитивная архитектура с онтологическими, эпистемологическими и аксиологическими рамками, реализованными через программные модули.

Система включает:
- многоуровневую память;
- модулирование когнитивных циклов;
- систему планирования;
- сенсорный, перцептивный и моторный слои;
- способность к анализу среды и взаимодействию с ней.

Проект реализуется на базе:

- NVIDIA Jetson Orin NX Super 16 GB  
- ARMv8 Processor rev 1 (v8l) × 8  
- NVIDIA Tegra Orin (nvgpu) / integrated GPU  
- Ubuntu 22.04.5 LTS (64-bit)

---

## Архитектура

Adam Chip — модульная событийно-ориентированная система, в которой:

- LLM отвечает за интерпретацию, reasoning и выбор действий;
- исполнение действий вынесено в Tool Layer;
- все модули связаны через оркестратор;
- система разделена на слои восприятия, мышления и действия.

### Архитектурные принципы

- разделение reasoning и execution  
- модульность и слабая связанность  
- локальность (edge-first)  
- воспроизводимость  
- расширяемость через абстракции  
- контроль над ресурсами (CPU/GPU/RAM)  

---

## Слои системы

### Interface Layer
- Telegram Bot (text + voice)
- Web / CLI (расширение)

### Perception Layer
- VAD (детекция речи)
- ASR (распознавание речи)
- Vision (on-demand / event-based)
- OCR / detection (расширение)

### Orchestrator
- центральный диспетчер системы
- маршрутизация событий
- управление очередями и приоритетами
- контроль состояния

### LLM Layer
- reasoning
- интерпретация намерений
- планирование действий
- работа через `LLMProvider`

### Skills Layer
- сценарии решения задач
- композиция действий
- управление последовательностями tool-вызовов

### Tool Layer
- строго определённые исполняемые действия:
  - заметки
  - работа с файлами
  - работа с камерой
  - системные операции (ограниченно)

### Memory System
- краткосрочная (контекст диалога)
- рабочая (текущая задача)
- долговременная:
  - заметки
  - документы
  - embeddings / RAG (в поздних версиях)

### Execution Layer
- выполнение действий
- взаимодействие с ОС и устройствами

### Output Layer
- текст
- голос (TTS)

### System Layer
- логирование
- телеметрия
- мониторинг
- конфигурация
- безопасность

---

## Инструменты (Tool Layer)

- `note_create`
- `note_search`
- `note_delete`
- `note_summarize`

В следующих версиях:
- файловые операции
- системные действия
- взаимодействие с устройствами
- внешние API

---

## Софт-стек

### Базовый

- Python
- FastAPI
- asyncio
- systemd

### AI / Inference

- `LLMProvider` (абстракция)
  - Ollama (v1)
  - llama.cpp (целевой runtime)
- whisper.cpp (ASR)
- Piper / Silero (TTS)

### Vision

- OpenCV
- ONNX Runtime / TensorRT

### Память

- v1: файловое хранилище (JSON / MD)
- v2: SQLite
- v3: Qdrant / Supabase (vector DB + RAG)

### Интеграции

- Telegram Bot API (text + voice)

---

## Связи между модулями

- [Mic / Camera / UI / Telegram]
- [VAD / ASR / Vision Capture]
- [Event Bus]
- [Dialogue Orchestrator]
    - [LLM Runtime]
    - [Memory Manager]
    - [Tool Router -> Validators -> Executors]
    - [Vision Service -> TensorRT/ONNX]
    - [TTS Service]
- [Responser]
    - [Text/Audio Output]
    - [Telegram]